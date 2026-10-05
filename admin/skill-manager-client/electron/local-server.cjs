const http = require("node:http");
const path = require("node:path");
const os = require("node:os");
const { promises: fs } = require("node:fs");
const crypto = require("node:crypto");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const execFileAsync = promisify(execFile);
const { ingestOtlp, readOtlpUsage } = require("./otlp-store.cjs");

const appRoot = path.resolve(__dirname, "..");
const staticRoot = path.join(appRoot, "dist", "client");
const skillsRoot = process.env.SKILLS_ROOT || path.join(os.homedir(), "Documents", "Me", "skills");
const metadataDir = path.join(skillsRoot, ".skill-manager");
const metadataPath = path.join(metadataDir, "tags.json");
const setsPath = path.join(metadataDir, "sets.json");
const softwareFactoryProfile = path.join(skillsRoot, "profiles", "software-factory");
const softwareFactoryManifestPath = path.join(softwareFactoryProfile, "software-factory-set.json");
const softwareFactoryLockPath = path.join(softwareFactoryProfile, "skills-lock.json");
const softwareFactoryRefreshScript = path.join(softwareFactoryProfile, "scripts", "refresh_set.py");
const usageConfigPath = path.join(os.homedir(), ".codex-usage", "config.json");
const otlpPort = Number(process.env.OTLP_PORT || 4318);
const otlpEndpoint = `http://127.0.0.1:${otlpPort}`;

async function resolveUsageServer() {
  const configured = process.env.SKILL_USAGE_SERVER || process.env.CODEX_USAGE_SERVER;
  if (configured) return configured.replace(/\/+$/, "");
  try {
    const config = JSON.parse(await fs.readFile(usageConfigPath, "utf8"));
    return String(config.server || "").trim().replace(/\/+$/, "") || null;
  } catch { return null; }
}

async function loadUsageSnapshot() {
  const otlp = await readOtlpUsage(skillsRoot);
  if (otlp.eventCount > 0) return { ...otlp, source: "otlp", otlpEndpoint };
  const server = await resolveUsageServer();
  if (!server) return { ...otlp, source: "otlp", otlpEndpoint, server: null, items: [], totalInvocations: 0 };
  try {
    const response = await fetch(new URL("/api/reports", `${server}/`).toString(), { signal: AbortSignal.timeout(1800) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const usage = data.skill_usage || data.usage?.skill_usage || {};
    const items = Array.isArray(usage.item_stats) ? usage.item_stats.map((item) => ({
      key: String(item.item_key || ""), name: String(item.display_name || item.item_key || ""),
      count: Number(item.total_invocations || 0), activeDays: Number(item.active_days || 0),
    })).filter((item) => item.key || item.name) : [];
    return { status: "connected", transport: "codex-usage-http", source: "codex-usage", server, otlpEndpoint, items, totalInvocations: Number(usage.summary?.total_invocations || items.reduce((sum, item) => sum + item.count, 0)), updatedAt: data.updated_at || null };
  } catch (error) {
    return { ...otlp, status: "idle", transport: "otlp/http", source: "otlp", server, otlpEndpoint, items: [], totalInvocations: 0, error: error.message };
  }
}

function attachUsage(skills, usage) {
  const byKey = new Map();
  for (const item of usage.items || []) {
    for (const value of [item.key, item.name]) if (value) byKey.set(value.toLowerCase(), item);
  }
  return skills.map((skill) => {
    const candidates = [skill.name, skill.id, skill.id.split("/").pop()];
    const match = candidates.map((value) => byKey.get(String(value).toLowerCase())).find(Boolean);
    return { ...skill, usageCount: match?.count || 0, usageActiveDays: match?.activeDays || 0, usageName: match?.name || null };
  });
}

async function loadTags() {
  try { return JSON.parse(await fs.readFile(metadataPath, "utf8")); } catch { return {}; }
}

async function loadSets() {
  try {
    const value = JSON.parse(await fs.readFile(setsPath, "utf8"));
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}

async function saveSets(sets) {
  await fs.mkdir(metadataDir, { recursive: true });
  await fs.writeFile(setsPath, `${JSON.stringify(sets, null, 2)}\n`, "utf8");
}

function normalizeSetPayload(payload, availableIds) {
  const name = String(payload?.name || "").trim();
  if (!name) throw new Error("Set 名称不能为空");
  const skillIds = [...new Set((Array.isArray(payload?.skillIds) ? payload.skillIds : []).map((id) => String(id)).filter((id) => availableIds.has(id)))];
  if (!skillIds.length) throw new Error("至少选择一个 Skill");
  return { name: name.slice(0, 80), skillIds };
}

function sanitizeSet(item) {
  return { id: String(item.id || ""), name: String(item.name || ""), skillIds: Array.isArray(item.skillIds) ? item.skillIds.map(String) : [], createdAt: item.createdAt || null, updatedAt: item.updatedAt || null };
}

async function readJsonFile(file, fallback = null) {
  try { return JSON.parse(await fs.readFile(file, "utf8")); } catch { return fallback; }
}

async function sha256(file) {
  return crypto.createHash("sha256").update(await fs.readFile(file)).digest("hex");
}

async function inspectFactoryEntry(entry) {
  const source = path.join(skillsRoot, "profiles", entry.source_profile, ".agents", "skills", entry.source_path);
  const target = path.join(softwareFactoryProfile, ".agents", "skills", entry.name);
  const sourceSkill = path.join(source, "SKILL.md");
  const targetSkill = path.join(target, "SKILL.md");
  let status = "missing-source";
  let sourceHash = null;
  let targetHash = null;
  try {
    sourceHash = await sha256(sourceSkill);
    try {
      targetHash = await sha256(targetSkill);
      status = sourceHash === targetHash ? "synced" : "drifted";
    } catch { status = "not-synced"; }
  } catch { /* status remains missing-source */ }
  return { ...entry, source: path.relative(skillsRoot, source), target: path.relative(skillsRoot, target), status, sourceHash, targetHash };
}

async function loadSoftwareFactory() {
  const manifest = await readJsonFile(softwareFactoryManifestPath, null);
  if (!manifest) return { available: false, error: "software-factory-set.json 不存在" };
  const lock = await readJsonFile(softwareFactoryLockPath, { version: 1, skills: {} });
  const base = Array.isArray(manifest.skills) ? manifest.skills : [];
  const packs = manifest.packs && typeof manifest.packs === "object" ? manifest.packs : {};
  const allEntries = [...base, ...Object.values(packs).flat()].reduce((map, entry) => map.set(entry.name, entry), new Map());
  const statuses = await Promise.all([...allEntries.values()].map(inspectFactoryEntry));
  const byName = new Map(statuses.map((entry) => [entry.name, entry]));
  const packData = Object.entries(packs).map(([name, entries]) => ({
    name,
    skills: entries.map((entry) => byName.get(entry.name) || entry),
    synced: entries.filter((entry) => byName.get(entry.name)?.status === "synced").length,
    total: entries.length,
  }));
  const counts = statuses.reduce((result, item) => { result[item.status] = (result[item.status] || 0) + 1; return result; }, {});
  return {
    available: true,
    profile: path.relative(skillsRoot, softwareFactoryProfile),
    manifest: { name: manifest.name, version: manifest.version, description: manifest.description, matt: manifest.matt, pstack: manifest.pstack },
    base: base.map((entry) => byName.get(entry.name) || entry),
    packs: packData,
    lock: { version: lock.version, count: Object.keys(lock.skills || {}).length },
    counts,
  };
}

async function runSoftwareFactoryRefresh(check = false) {
  // Skill Atlas scans concrete skill directories. Keep client refreshes in
  // copy mode so profiles remain portable and discoverable by the client.
  const args = [softwareFactoryRefreshScript, "--repo", skillsRoot, "--mode", "copy"];
  if (check) args.push("--check");
  const result = await execFileAsync("python3", args, { cwd: skillsRoot, maxBuffer: 1024 * 1024 * 4 });
  return { output: result.stdout || "", error: result.stderr || "" };
}

async function walk(dir, result = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if ([".git", "node_modules", "dist", "target", ".skill-manager"].includes(entry.name) || entry.isSymbolicLink()) continue;
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(absolute, result);
    else if (entry.isFile() && entry.name === "SKILL.md") result.push(absolute);
  }
  return result;
}

function parseSkill(markdown) {
  const frontmatter = markdown.match(/^---\s*\n([\s\S]*?)\n---/);
  const values = {};
  for (const line of (frontmatter?.[1] || "").split("\n")) {
    const match = line.match(/^([\w-]+):\s*["']?(.+?)["']?\s*$/);
    if (match) values[match[1]] = match[2];
  }
  const heading = markdown.match(/^#\s+(.+)$/m)?.[1];
  return { name: values.name || heading || "Untitled skill", description: values.description || "", frontmatter: Boolean(frontmatter) };
}

async function listSkills() {
  const tags = await loadTags();
  const usage = await loadUsageSnapshot();
  const files = await walk(skillsRoot);
  const skills = await Promise.all(files.map(async (file) => {
    const relative = path.relative(skillsRoot, file).split(path.sep).join("/");
    const markdown = await fs.readFile(file, "utf8");
    const parsed = parseSkill(markdown);
    const id = relative.slice(0, -"/SKILL.md".length);
    const category = id.startsWith("profiles/") ? id.split("/")[1] || "root" : id.split("/")[0] || "root";
    return { id, path: file, name: parsed.name, description: parsed.description, category, tags: tags[id] || [], updatedAt: (await fs.stat(file)).mtimeMs, size: Buffer.byteLength(markdown), frontmatter: parsed.frontmatter };
  }));
  skills.sort((a, b) => a.name.localeCompare(b.name));
  return { root: skillsRoot, skills: attachUsage(skills, usage), categories: [...new Set(skills.map((skill) => skill.category))].sort(), usage };
}

function json(res, status, payload) {
  res.statusCode = status; res.setHeader("Content-Type", "application/json; charset=utf-8"); res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => { let body = ""; req.on("data", (chunk) => { body += chunk; }); req.on("end", () => resolve(body)); req.on("error", reject); });
}

function readBodyBuffer(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function api(req, res, pathname) {
  const otlpMatch = pathname.match(/^\/v1\/(traces|logs|metrics)$/);
  if (otlpMatch && req.method === "POST") {
    const result = await ingestOtlp({ skillsRoot, signal: otlpMatch[1], body: await readBodyBuffer(req), contentType: req.headers["content-type"] || "" });
    return json(res, 200, { partialSuccess: {}, ...result });
  }
  if (pathname === "/api/usage/" && req.method === "GET") return json(res, 200, await loadUsageSnapshot());
  if (pathname === "/api/software-factory/" && req.method === "GET") return json(res, 200, await loadSoftwareFactory());
  if (pathname === "/api/software-factory/check/" && req.method === "POST") {
    const result = await runSoftwareFactoryRefresh(true);
    return json(res, 200, { ok: true, action: "check", ...result, factory: await loadSoftwareFactory() });
  }
  if (pathname === "/api/software-factory/refresh/" && req.method === "POST") {
    const result = await runSoftwareFactoryRefresh(false);
    return json(res, 200, { ok: true, action: "refresh", ...result, factory: await loadSoftwareFactory() });
  }
  if (pathname === "/api/sets/" && req.method === "GET") {
    const current = await listSkills();
    const available = new Set(current.skills.map((skill) => skill.id));
    const sets = (await loadSets()).map(sanitizeSet).map((set) => ({ ...set, skillIds: set.skillIds.filter((id) => available.has(id)) }));
    return json(res, 200, { sets });
  }
  if (pathname === "/api/sets/" && req.method === "POST") {
    const current = await listSkills();
    const payload = normalizeSetPayload(JSON.parse(await readBody(req) || "{}"), new Set(current.skills.map((skill) => skill.id)));
    const now = new Date().toISOString();
    const set = { id: `set-${Date.now().toString(36)}`, ...payload, createdAt: now, updatedAt: now };
    await saveSets([...(await loadSets()), set]);
    return json(res, 201, { set });
  }
  const setMatch = pathname.match(/^\/api\/sets\/([^/]+)$/);
  if (setMatch) {
    const setId = decodeURIComponent(setMatch[1]);
    const sets = await loadSets(); const index = sets.findIndex((set) => String(set.id) === setId);
    if (index < 0) throw new Error("Set not found");
    if (req.method === "DELETE") { sets.splice(index, 1); await saveSets(sets); return json(res, 200, { id: setId }); }
    if (req.method === "PUT") {
      const current = await listSkills();
      const base = { ...sets[index], ...JSON.parse(await readBody(req) || "{}") };
      const payload = normalizeSetPayload(base, new Set(current.skills.map((skill) => skill.id)));
      sets[index] = { ...sets[index], ...payload, updatedAt: new Date().toISOString() };
      await saveSets(sets); return json(res, 200, { set: sets[index] });
    }
  }
  const openMatch = pathname.match(/^\/api\/skills\/([^/]+)\/open$/);
  if (openMatch && req.method === "POST") {
    const id = decodeURIComponent(openMatch[1]);
    const current = await listSkills();
    const skill = current.skills.find((item) => item.id === id);
    if (!skill) throw new Error("Skill not found");
    await execFileAsync("open", [path.dirname(skill.path)]);
    return json(res, 200, { id, path: path.dirname(skill.path) });
  }
  if (pathname === "/api/skills/" && req.method === "GET") return json(res, 200, await listSkills());
  if (pathname === "/api/skills/" && req.method === "POST") {
    const payload = JSON.parse(await readBody(req) || "{}");
    const name = String(payload.name || "").trim();
    const category = String(payload.category || "").trim();
    const description = String(payload.description || "").trim();
    if (!/^[A-Za-z0-9_\-一-龥]+$/.test(name) || !/^[A-Za-z0-9_\-一-龥]+$/.test(category)) throw new Error("名称和分类只能使用中文、字母、数字、下划线或短横线");
    const target = path.resolve(skillsRoot, category, name);
    if (!target.startsWith(`${path.resolve(skillsRoot)}${path.sep}`)) throw new Error("目标路径无效");
    try { await fs.stat(target); throw new Error("同名 Skill 已存在"); } catch (error) { if (error.message === "同名 Skill 已存在") throw error; }
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.mkdir(target);
    const markdown = `---\nname: ${name}\ndescription: ${description || "本地 Skill"}\n---\n\n# ${name}\n\n${description || "在这里补充 Skill 的使用说明。"}\n`;
    await fs.writeFile(path.join(target, "SKILL.md"), markdown, "utf8");
    const tags = [...new Set((Array.isArray(payload.tags) ? payload.tags : []).map((tag) => String(tag).trim()).filter(Boolean))].slice(0, 20);
    if (tags.length) { const next = await loadTags(); next[`${category}/${name}`] = tags; await fs.mkdir(metadataDir, { recursive: true }); await fs.writeFile(metadataPath, `${JSON.stringify(next, null, 2)}\n`); }
    return json(res, 201, { id: `${category}/${name}` });
  }
  const tagsMatch = pathname.match(/^\/api\/skills\/([^/]+)\/tags$/);
  if (tagsMatch && req.method === "PUT") {
    const id = decodeURIComponent(tagsMatch[1]);
    const current = await listSkills();
    if (!current.skills.some((skill) => skill.id === id)) throw new Error("Skill not found");
    const payload = JSON.parse(await readBody(req) || "{}");
    const tags = [...new Set((Array.isArray(payload.tags) ? payload.tags : []).map((tag) => String(tag).trim()).filter(Boolean))].slice(0, 20);
    const next = await loadTags(); next[id] = tags;
    await fs.mkdir(metadataDir, { recursive: true }); await fs.writeFile(metadataPath, `${JSON.stringify(next, null, 2)}\n`);
    return json(res, 200, { id, tags });
  }
  const previewMatch = pathname.match(/^\/api\/skills\/([^/]+)\/preview$/);
  if (previewMatch && req.method === "GET") {
    const id = decodeURIComponent(previewMatch[1]);
    const current = await listSkills(); const skill = current.skills.find((item) => item.id === id);
    if (!skill) throw new Error("Skill not found");
    return json(res, 200, { markdown: await fs.readFile(skill.path, "utf8") });
  }
  return false;
}

function contentType(file) {
  return { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json" }[path.extname(file)] || "application/octet-stream";
}

async function serveStatic(req, res, pathname) {
  let file = path.resolve(staticRoot, `.${pathname === "/" ? "/index.html" : pathname}`);
  if (!file.startsWith(`${staticRoot}${path.sep}`)) return json(res, 403, { error: "Forbidden" });
  try { const stat = await fs.stat(file); if (!stat.isFile()) throw new Error("not file"); }
  catch { if (req.method === "GET" && req.headers.accept?.includes("text/html")) file = path.join(staticRoot, "index.html"); else return json(res, 404, { error: "Not found" }); }
  res.statusCode = 200; res.setHeader("Content-Type", contentType(file)); res.end(req.method === "HEAD" ? undefined : await fs.readFile(file));
}

function startServer() {
  const handler = async (req, res) => {
    try {
      const url = new URL(req.url, "http://127.0.0.1");
      if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) { const handled = await api(req, res, url.pathname); if (!handled && !res.writableEnded) json(res, 404, { error: "Not found" }); return; }
      await serveStatic(req, res, url.pathname);
    } catch (error) { if (!res.writableEnded) json(res, 400, { error: error.message }); }
  };
  const server = http.createServer(handler);
  const otlpServer = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://127.0.0.1");
      if (!url.pathname.startsWith("/v1/")) return json(res, 404, { error: "Not found" });
      const handled = await api(req, res, url.pathname);
      if (!handled && !res.writableEnded) json(res, 404, { error: "Not found" });
    } catch (error) { if (!res.writableEnded) json(res, 400, { error: error.message }); }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      otlpServer.once("error", (error) => { if (error.code === "EADDRINUSE") { console.warn(`OTLP port ${otlpPort} is busy; OTLP receiver is unavailable`); resolve({ server, otlpServer: null, port: server.address().port, otlpPort: null }); } else reject(error); });
      otlpServer.listen(otlpPort, "127.0.0.1", () => resolve({ server, otlpServer, port: server.address().port, otlpPort }));
    });
  });
}

module.exports = { startServer };
