const cp = require("child_process");

function ensureMcporter() {
  try {
    cp.execFileSync("mcporter", ["--version"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    if (error.code === "ENOENT") {
      throw new Error("mcporter not found in PATH");
    }
    throw new Error(`mcporter is not ready: ${error.message}`);
  }
}

function mcporterList(target) {
  return cp.execFileSync("mcporter", ["list", target, "--schema"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function mcporterCall(target, toolName, payload) {
  const raw = cp.execFileSync("mcporter", ["call", target, toolName, "--args", JSON.stringify(payload)], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return raw;
}

function safeJson(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function setPath(target, dottedKey, value) {
  if (!dottedKey.includes(".")) {
    target[dottedKey] = value;
    return;
  }
  const parts = dottedKey.split(".");
  let cursor = target;
  for (let i = 0; i < parts.length - 1; i += 1) {
    const part = parts[i];
    if (!Object.prototype.hasOwnProperty.call(cursor, part) || typeof cursor[part] !== "object") {
      cursor[part] = {};
    }
    cursor = cursor[part];
  }
  cursor[parts[parts.length - 1]] = value;
}

function resolveTemplateValue(raw, context) {
  if (typeof raw !== "string" || !raw.startsWith("$")) {
    return raw;
  }
  return context[raw.slice(1)] ?? null;
}

function renderArgs(templateArgs, context) {
  const payload = {};
  for (const [key, rawValue] of Object.entries(templateArgs || {})) {
    const value = resolveTemplateValue(rawValue, context);
    if (value !== null && value !== undefined) {
      setPath(payload, key, value);
    }
  }
  return payload;
}

function extractNodeId(value) {
  if (!value) {
    return null;
  }
  if (typeof value === "string") {
    const urlMatch = value.match(/\/nodes\/([A-Za-z0-9]+)/);
    if (urlMatch) {
      return urlMatch[1];
    }
    if (/^[A-Za-z0-9]{20,}$/.test(value)) {
      return value;
    }
    return value;
  }
  if (typeof value === "object") {
    return (
      extractNodeId(value.nodeId) ||
      extractNodeId(value.dentryUuid) ||
      extractNodeId(value.id) ||
      extractNodeId(value.url) ||
      extractNodeId(value.link)
    );
  }
  return null;
}

function findNodeIdDeep(payload) {
  if (!payload || typeof payload !== "object") {
    return extractNodeId(payload);
  }
  const direct =
    extractNodeId(payload.nodeId) ||
    extractNodeId(payload.dentryUuid) ||
    extractNodeId(payload.url);
  if (direct) {
    return direct;
  }
  for (const value of Object.values(payload)) {
    const found = findNodeIdDeep(value);
    if (found) {
      return found;
    }
  }
  return null;
}

module.exports = {
  ensureMcporter,
  mcporterList,
  mcporterCall,
  safeJson,
  renderArgs,
  findNodeIdDeep,
};
