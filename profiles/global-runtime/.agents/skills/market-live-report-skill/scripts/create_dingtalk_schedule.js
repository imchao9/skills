#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const cp = require("child_process");

const DEFAULT_ADAPTER = path.resolve(
  __dirname,
  "../references/dingtalk-calendar-adapter.example.json",
);
const DEFAULT_USER_MAP = path.resolve(
  __dirname,
  "../references/user-id-map.local.json",
);

function parseArgs(argv) {
  const args = {
    payload: null,
    adapter: DEFAULT_ADAPTER,
    userMap: DEFAULT_USER_MAP,
    target: process.env.DINGTALK_CALENDAR_TARGET || "钉钉日历",
    pretty: false,
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--payload":
        args.payload = argv[++i];
        break;
      case "--adapter":
        args.adapter = argv[++i];
        break;
      case "--user-map":
        args.userMap = argv[++i];
        break;
      case "--target":
        args.target = argv[++i];
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.payload) {
    throw new Error("pass --payload <file>");
  }
  return args;
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function loadOptionalJson(filePath) {
  if (!filePath || !fs.existsSync(filePath)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

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
  return cp.execFileSync("mcporter", ["call", target, toolName, "--args", JSON.stringify(payload)], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
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

function toIsoOffset(localDateTime) {
  const [datePart, timePart] = String(localDateTime).split(" ");
  if (!datePart || !timePart) {
    throw new Error(`invalid local datetime: ${localDateTime}`);
  }
  return `${datePart}T${timePart}:00+08:00`;
}

function extractEventId(result) {
  if (!result || typeof result !== "object") {
    return null;
  }
  return result.eventId || result.id || result.data?.eventId || result.result?.eventId || result.result?.id || null;
}

function normalizeCalendarUserId(raw) {
  const value = String(raw || "").trim();
  if (!value) {
    return "";
  }
  return value.replace(/^userId_/i, "");
}

function mapAttendeesToIds(attendees, userMap) {
  const resolved = [];
  const unresolved = [];
  for (const name of attendees || []) {
    const userId = userMap[name];
    if (userId) {
      resolved.push(normalizeCalendarUserId(userId));
    } else {
      unresolved.push(name);
    }
  }
  return {
    attendeeIds: [...new Set(resolved)],
    unresolved,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const adapter = loadJson(args.adapter);
  const userMap = loadOptionalJson(args.userMap);
  const payload = loadJson(args.payload);
  const { attendeeIds, unresolved } = mapAttendeesToIds(payload.attendees || [], userMap);

  const context = {
    summary: payload.title,
    startDateTime: toIsoOffset(payload.start_at),
    endDateTime: toIsoOffset(payload.end_at),
    timeZone: payload.timezone || "Asia/Shanghai",
    description: payload.description || "",
    freeBusy: "busy",
    attendeeIds,
  };

  const summary = {
    target: args.target,
    adapter: path.resolve(args.adapter),
    summary: context.summary,
    startDateTime: context.startDateTime,
    endDateTime: context.endDateTime,
    attendees: payload.attendees || [],
    attendeeIds,
    unresolved_attendees: unresolved,
  };

  if (args.dryRun) {
    process.stdout.write(JSON.stringify(summary, null, args.pretty ? 2 : 0));
    if (args.pretty) {
      process.stdout.write("\n");
    }
    return;
  }

  ensureMcporter();
  const schemaText = mcporterList(args.target);
  const createTool = adapter.tools.create_calendar_event;
  if (!schemaText.includes(createTool.name)) {
    throw new Error(`configured tool is missing from MCP schema: ${createTool.name}`);
  }

  const result = {
    ...summary,
    actions: [],
  };

  const createArgs = renderArgs(createTool.args, context);
  const createOutput = safeJson(mcporterCall(args.target, createTool.name, createArgs));
  result.actions.push({
    tool: createTool.name,
    args: createArgs,
    output: createOutput,
  });

  const eventId = extractEventId(createOutput);
  const attendees = attendeeIds || [];
  const participantTool = adapter.tools.add_calendar_participant;
  if (eventId && attendees.length && schemaText.includes(participantTool.name)) {
    const participantArgs = renderArgs(participantTool.args, {
      eventId,
      attendeesToAdd: attendees,
    });
    result.actions.push({
      tool: participantTool.name,
      args: participantArgs,
      output: safeJson(mcporterCall(args.target, participantTool.name, participantArgs)),
    });
    result.eventId = eventId;
  } else {
    result.eventId = eventId;
    result.attendees_skipped = attendees;
  }

  process.stdout.write(JSON.stringify(result, null, args.pretty ? 2 : 0));
  if (args.pretty) {
    process.stdout.write("\n");
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
}
