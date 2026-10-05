import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const execFileAsync = promisify(execFile);

const require = createRequire(import.meta.url);
const { ingestOtlp, readOtlpUsage } = require("./electron/otlp-store.cjs");

const appRoot = path.dirname(new URL(import.meta.url).pathname);
const skillsRoot = process.env.SKILLS_ROOT || path.resolve(appRoot, "../..");
const metadataDir = path.join(skillsRoot, ".skill-manager");
const metadataPath = path.join(metadataDir, "tags.json");
const setsPath = path.join(metadataDir, "sets.json");
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

async function walk(dir, result = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if ([".git", "node_modules", "dist", "target", ".skill-manager"].includes(entry.name)) continue;
    if (entry.isSymbolicLink()) continue;
    const absolute = path.join(dir, entry.name);
    const stat = await fs.stat(absolute);
    if (stat.isDirectory()) await walk(absolute, result);
    else if (stat.isFile() && entry.name === "SKILL.md") result.push(absolute);
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

function skillsManagerApi() {
  return { name: "skills-manager-api", configureServer(server) {
    server.middlewares.use("/v1", async (req, res, next) => {
      const match = req.url?.match(/^\/(traces|logs|metrics)$/);
      if (!match || req.method !== "POST") { next(); return; }
      try {
        const chunks = []; for await (const chunk of req) chunks.push(chunk);
        const result = await ingestOtlp({ skillsRoot, signal: match[1], body: Buffer.concat(chunks), contentType: req.headers["content-type"] || "" });
        res.statusCode = 200; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ partialSuccess: {}, ...result }));
      } catch (error) { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ error: "invalid_otlp", message: error.message })); }
    });
    server.middlewares.use("/api/usage", async (req, res, next) => {
      if (req.url === "/" && req.method === "GET") {
        res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(await loadUsageSnapshot())); return;
      }
      next();
    });
    server.middlewares.use("/api/sets", async (req, res, next) => {
      const pathname = new URL(req.url || "/", "http://127.0.0.1").pathname;
      if (pathname === "/" && req.method === "GET") {
        const current = await listSkills();
        const available = new Set(current.skills.map((skill) => skill.id));
        const sets = (await loadSets()).map(sanitizeSet).map((set) => ({ ...set, skillIds: set.skillIds.filter((id) => available.has(id)) }));
        res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ sets })); return;
      }
      if (pathname === "/" && req.method === "POST") {
        let body = ""; req.on("data", (chunk) => { body += chunk; });
        req.on("end", async () => {
          try {
            const current = await listSkills();
            const payload = normalizeSetPayload(JSON.parse(body || "{}"), new Set(current.skills.map((skill) => skill.id)));
            const now = new Date().toISOString();
            const set = { id: `set-${Date.now().toString(36)}`, ...payload, createdAt: now, updatedAt: now };
            await saveSets([...(await loadSets()), set]);
            res.statusCode = 201; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ set }));
          } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: error.message })); }
        }); return;
      }
      const setId = decodeURIComponent(pathname.slice(1));
      if (!setId) { next(); return; }
      const sets = await loadSets(); const index = sets.findIndex((set) => String(set.id) === setId);
      if (index < 0) { res.statusCode = 404; res.end(JSON.stringify({ error: "Set not found" })); return; }
      if (req.method === "DELETE") { sets.splice(index, 1); await saveSets(sets); res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ id: setId })); return; }
      if (req.method === "PUT") {
        let body = ""; req.on("data", (chunk) => { body += chunk; });
        req.on("end", async () => {
          try { const current = await listSkills(); const base = { ...sets[index], ...JSON.parse(body || "{}") }; const payload = normalizeSetPayload(base, new Set(current.skills.map((skill) => skill.id))); sets[index] = { ...sets[index], ...payload, updatedAt: new Date().toISOString() }; await saveSets(sets); res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ set: sets[index] })); }
          catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: error.message })); }
        }); return;
      }
      next();
    });
    server.middlewares.use("/api/skills", async (req, res, next) => {
      if (req.url === "/" && req.method === "GET") {
        try { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(await listSkills())); } catch (error) { res.statusCode = 500; res.end(JSON.stringify({ error: error.message })); }
        return;
      }
      if (req.url === "/" && req.method === "POST") {
        let body = "";
        req.on("data", (chunk) => { body += chunk; });
        req.on("end", async () => {
          try {
            const payload = JSON.parse(body || "{}");
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
            const next = await loadTags();
            const tags = [...new Set((Array.isArray(payload.tags) ? payload.tags : []).map((tag) => String(tag).trim()).filter(Boolean))].slice(0, 20);
            if (tags.length) { next[`${category}/${name}`] = tags; await fs.mkdir(metadataDir, { recursive: true }); await fs.writeFile(metadataPath, `${JSON.stringify(next, null, 2)}\n`); }
            res.setHeader("Content-Type", "application/json"); res.statusCode = 201; res.end(JSON.stringify({ id: `${category}/${name}` }));
          } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: error.code === "EEXIST" ? "同名 Skill 已存在" : error.message })); }
        });
        return;
      }
      const openMatch = req.url?.match(/^\/([^/]+)\/open$/);
      if (openMatch && req.method === "POST") {
        try {
          const id = decodeURIComponent(openMatch[1]);
          const current = await listSkills(); const skill = current.skills.find((item) => item.id === id);
          if (!skill) throw new Error("Skill not found");
          await execFileAsync("open", [path.dirname(skill.path)]);
          res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ id, path: path.dirname(skill.path) }));
        } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: error.message })); }
        return;
      }
      const match = req.url?.match(/^\/([^/]+)\/tags$/);
      if (match && req.method === "PUT") {
        const id = decodeURIComponent(match[1]);
        let body = "";
        req.on("data", (chunk) => { body += chunk; });
        req.on("end", async () => {
          try {
            const current = await listSkills();
            if (!current.skills.some((skill) => skill.id === id)) throw new Error("Skill not found");
            const payload = JSON.parse(body || "{}");
            const tags = [...new Set((Array.isArray(payload.tags) ? payload.tags : []).map((tag) => String(tag).trim()).filter(Boolean))].slice(0, 20);
            const next = await loadTags(); next[id] = tags;
            await fs.mkdir(metadataDir, { recursive: true });
            await fs.writeFile(metadataPath, `${JSON.stringify(next, null, 2)}\n`);
            res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ id, tags }));
          } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ error: error.message })); }
        });
        return;
      }
      const preview = req.url?.match(/^\/([^/]+)\/preview$/);
      if (preview && req.method === "GET") {
        try {
          const id = decodeURIComponent(preview[1]);
          const current = await listSkills();
          const skill = current.skills.find((item) => item.id === id);
          if (!skill) throw new Error("Skill not found");
          const markdown = await fs.readFile(skill.path, "utf8");
          res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ markdown }));
        } catch (error) { res.statusCode = 404; res.end(JSON.stringify({ error: error.message })); }
        return;
      }
      next();
    });
  }};
}

export default defineConfig({
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local"],
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  plugins: [skillsManagerApi(), react()],
});
