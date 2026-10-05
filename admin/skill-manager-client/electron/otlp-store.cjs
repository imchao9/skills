const crypto = require("node:crypto");
const path = require("node:path");
const { promises: fs } = require("node:fs");

function storePath(skillsRoot) {
  return path.join(skillsRoot, ".skill-manager", "otlp-events.jsonl");
}

function attrValue(value) {
  if (!value || typeof value !== "object") return value;
  for (const key of ["stringValue", "string_value", "intValue", "int_value", "doubleValue", "double_value", "boolValue", "bool_value"]) {
    if (value[key] !== undefined) return value[key];
  }
  return value;
}

function attrsToObject(attrs) {
  const result = {};
  for (const entry of attrs || []) {
    if (!entry?.key) continue;
    result[String(entry.key)] = attrValue(entry.value);
  }
  return result;
}

function valueFromProto(bytes) {
  const reader = new Reader(bytes);
  let value = null;
  while (!reader.end()) {
    const { field, wire } = reader.tag();
    if (wire === 2 && field === 1) value = reader.string();
    else if (wire === 0 && field === 2) value = Boolean(reader.varint());
    else if (wire === 0 && field === 3) value = reader.varint();
    else if (wire === 1 && field === 4) value = reader.double();
    else if (wire === 2 && field === 7) value = Buffer.from(reader.bytes()).toString("base64");
    else reader.skip(wire);
  }
  return value;
}

function protoAttrs(bytes) {
  const reader = new Reader(bytes);
  const result = {};
  while (!reader.end()) {
    const { field, wire } = reader.tag();
    if (field === 1 && wire === 2) {
      const entry = new Reader(reader.bytes());
      let key = ""; let value;
      while (!entry.end()) {
        const item = entry.tag();
        if (item.field === 1 && item.wire === 2) key = entry.string();
        else if (item.field === 2 && item.wire === 2) value = valueFromProto(entry.bytes());
        else entry.skip(item.wire);
      }
      if (key) result[key] = value;
    } else reader.skip(wire);
  }
  return result;
}

function readTimestamp(value) {
  if (typeof value === "bigint") return new Date(Number(value / 1000000n)).toISOString();
  if (typeof value === "string" && /^\d+$/.test(value)) return new Date(Number(BigInt(value) / 1000000n)).toISOString();
  if (typeof value === "number" && value > 1e12) return new Date(value / 1e6).toISOString();
  return new Date().toISOString();
}

function parseJson(signal, payload) {
  const events = [];
  const resources = signal === "traces" ? payload.resourceSpans || payload.resource_spans || [] : signal === "logs" ? payload.resourceLogs || payload.resource_logs || [] : [];
  for (const resourceItem of resources) {
    const resource = attrsToObject(resourceItem.resource?.attributes);
    const scopes = signal === "traces" ? resourceItem.scopeSpans || resourceItem.scope_spans || [] : resourceItem.scopeLogs || resourceItem.scope_logs || [];
    for (const scope of scopes) {
      const records = signal === "traces" ? scope.spans || [] : scope.logRecords || scope.log_records || [];
      for (const record of records) {
        const attrs = attrsToObject(record.attributes);
        const name = String(record.name || record.eventName || record.event_name || attrValue(record.body) || "");
        const skillName = findSkillName(name, attrs);
        if (!skillName) continue;
        events.push({ signal, name, skillName, attributes: attrs, serviceName: resource["service.name"] || null, traceId: record.traceId || record.trace_id || null, spanId: record.spanId || record.span_id || null, timestamp: readTimestamp(record.startTimeUnixNano || record.start_time_unix_nano || record.timeUnixNano || record.time_unix_nano) });
      }
    }
  }
  return events;
}

function findSkillName(name, attrs) {
  const candidate = attrs["skill.name"] || attrs.skill_name || attrs["skill.id"] || attrs["gen_ai.tool.name"] || attrs["tool.name"];
  if (candidate) return String(candidate);
  const match = String(name).match(/^(?:skill[.:/]|invoke[_ .:-]?skill[.:/])(.+)$/i);
  return match ? match[1].trim() : null;
}

class Reader {
  constructor(buffer) { this.buffer = Buffer.from(buffer); this.pos = 0; }
  end() { return this.pos >= this.buffer.length; }
  varint() { let value = 0n; let shift = 0n; while (this.pos < this.buffer.length) { const byte = this.buffer[this.pos++]; value |= BigInt(byte & 127) << shift; if (!(byte & 128)) return value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value; shift += 7n; } throw new Error("truncated protobuf varint"); }
  tag() { const value = Number(this.varint()); return { field: value >>> 3, wire: value & 7 }; }
  bytes() { const length = Number(this.varint()); const end = this.pos + length; if (end > this.buffer.length) throw new Error("truncated protobuf bytes"); const value = this.buffer.subarray(this.pos, end); this.pos = end; return value; }
  string() { return Buffer.from(this.bytes()).toString("utf8"); }
  double() { const value = this.buffer.readDoubleLE(this.pos); this.pos += 8; return value; }
  fixed64() { const value = this.buffer.readBigUInt64LE(this.pos); this.pos += 8; return value; }
  skip(wire) { if (wire === 0) this.varint(); else if (wire === 1) this.pos += 8; else if (wire === 2) this.bytes(); else if (wire === 5) this.pos += 4; else throw new Error(`unsupported protobuf wire type ${wire}`); }
}

function parseProto(signal, buffer) {
  const root = new Reader(buffer);
  const events = [];
  while (!root.end()) {
    const { field, wire } = root.tag();
    if (field !== 1 || wire !== 2) { root.skip(wire); continue; }
    const resourceContainer = new Reader(root.bytes());
    let resourceAttrs = {};
    const records = [];
    while (!resourceContainer.end()) {
      const item = resourceContainer.tag();
      if (item.field === 1 && item.wire === 2) {
        resourceAttrs = protoAttrs(resourceContainer.bytes());
      } else if (item.field === 2 && item.wire === 2) {
        const scopeContainer = new Reader(resourceContainer.bytes());
        while (!scopeContainer.end()) {
          const scopeItem = scopeContainer.tag();
          if (scopeItem.field === 2 && scopeItem.wire === 2) records.push(scopeContainer.bytes()); else scopeContainer.skip(scopeItem.wire);
        }
      } else resourceContainer.skip(item.wire);
    }
    for (const recordBytes of records) {
      const record = new Reader(recordBytes); let name = ""; let timestamp; let attrs = {}; let traceId = null; let spanId = null;
      while (!record.end()) {
        const item = record.tag();
        if (item.field === 5 && item.wire === 2 && signal === "traces") name = record.string();
        else if ((item.field === 4 || item.field === 12) && item.wire === 2 && signal === "logs") name = record.string();
        else if (item.field === 5 && item.wire === 2 && signal === "logs") name = String(valueFromProto(record.bytes()) || "");
        else if ((item.field === 7 || item.field === 1) && item.wire === 1) timestamp = record.fixed64();
        else if (item.field === 1 && item.wire === 2 && signal === "traces") { traceId = Buffer.from(record.bytes()).toString("hex"); }
        else if (item.field === 2 && item.wire === 2 && signal === "traces") { spanId = Buffer.from(record.bytes()).toString("hex"); }
        else if (item.field === 9 && item.wire === 2 && signal === "logs") { record.bytes(); }
        else if (item.field === 9 && item.wire === 2) attrs = { ...attrs, ...protoAttrs(record.bytes()) };
        else if (item.field === 6 && item.wire === 2 && signal === "logs") attrs = { ...attrs, ...protoAttrs(record.bytes()) };
        else record.skip(item.wire);
      }
      const skillName = findSkillName(name, { ...resourceAttrs, ...attrs });
      if (skillName) events.push({ signal, name, skillName, attributes: attrs, serviceName: resourceAttrs["service.name"] || null, traceId, spanId, timestamp: readTimestamp(timestamp) });
    }
  }
  return events;
}

async function ingestOtlp({ skillsRoot, signal, body, contentType }) {
  const events = String(contentType || "").includes("json") ? parseJson(signal, JSON.parse(Buffer.from(body).toString("utf8") || "{}")) : parseProto(signal, body);
  if (!events.length) return { accepted: 0, total: await countEvents(skillsRoot) };
  const target = storePath(skillsRoot);
  await fs.mkdir(path.dirname(target), { recursive: true });
  const lines = events.map((event) => {
    const identity = event.traceId || event.spanId ? [event.signal, event.traceId, event.spanId, event.name, event.skillName] : [event.signal, event.name, event.skillName, event.timestamp];
    const eventId = crypto.createHash("sha256").update(JSON.stringify(identity)).digest("hex").slice(0, 24);
    return JSON.stringify({ ...event, eventId, receivedAt: new Date().toISOString() });
  });
  const existing = await readEvents(skillsRoot);
  const seen = new Set(existing.map((event) => event.eventId));
  const fresh = lines.filter((line) => !seen.has(JSON.parse(line).eventId));
  if (fresh.length) await fs.appendFile(target, `${fresh.join("\n")}\n`, "utf8");
  return { accepted: fresh.length, duplicate: events.length - fresh.length, total: existing.length + fresh.length };
}

async function readEvents(skillsRoot) {
  try {
    const lines = (await fs.readFile(storePath(skillsRoot), "utf8")).split("\n").filter(Boolean);
    return lines.map((line) => JSON.parse(line)).filter((event) => event && event.eventId);
  } catch { return []; }
}

async function countEvents(skillsRoot) { return (await readEvents(skillsRoot)).length; }

async function readOtlpUsage(skillsRoot) {
  const events = await readEvents(skillsRoot);
  const bySkill = new Map();
  for (const event of events) {
    const current = bySkill.get(event.skillName) || { key: event.skillName, name: event.skillName, count: 0, activeDays: new Set() };
    current.count += 1;
    current.activeDays.add(String(event.timestamp || event.receivedAt).slice(0, 10));
    bySkill.set(event.skillName, current);
  }
  const items = [...bySkill.values()].map((item) => ({ key: item.key, name: item.name, count: item.count, activeDays: item.activeDays.size })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  return { status: events.length ? "connected" : "idle", transport: "otlp/http", items, totalInvocations: events.length, eventCount: events.length, lastReceivedAt: events.at(-1)?.receivedAt || null };
}

module.exports = { ingestOtlp, readOtlpUsage };
