#!/usr/bin/env node

const fs = require("fs");
const { parseText } = require("./parse_live_report");

function parseArgs(argv) {
  const args = {
    parsed: null,
    raw: null,
    pretty: false,
    year: new Date().getFullYear(),
    durationMinutes: 60,
    reminderMinutesBefore: 30,
    attendees: [],
    notifyOnlyDuty: false,
    fixedAttendee: "胡露",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--parsed":
        args.parsed = argv[++i];
        break;
      case "--raw":
        args.raw = argv[++i];
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--duration-minutes":
        args.durationMinutes = Number(argv[++i]);
        break;
      case "--reminder-minutes":
        args.reminderMinutesBefore = Number(argv[++i]);
        break;
      case "--attendees":
        args.attendees = splitPeople(argv[++i]);
        break;
      case "--fixed-attendee":
        args.fixedAttendee = argv[++i].trim().replace(/^@+/, "");
        break;
      case "--notify-only-duty":
        args.notifyOnlyDuty = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.parsed && !args.raw) {
    throw new Error("pass --parsed <file> or --raw <file>");
  }
  return args;
}

function readPayload(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  const text = fs.readFileSync(args.raw, "utf8");
  return parseText(text, args.year);
}

function splitPeople(value) {
  return String(value)
    .split(/[，,、]/)
    .map((part) => part.trim().replace(/^@+/, ""))
    .filter(Boolean);
}

function pad(num) {
  return String(num).padStart(2, "0");
}

function buildDateTime(dateStr, timeStr) {
  const [year, month, day] = dateStr.split("-").map(Number);
  const [hour, minute] = timeStr.split(":").map(Number);
  return new Date(year, month - 1, day, hour, minute, 0, 0);
}

function formatLocal(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function addMinutes(date, minutes) {
  return new Date(date.getTime() + minutes * 60000);
}

function inferLiveVersion(payload) {
  const explicit = String(payload?.meta?.live_version || "").trim();
  if (explicit) {
    return explicit;
  }

  const requestTitle = String(payload?.meta?.request_title || "");
  if (requestTitle.includes("稳定版") || requestTitle.includes("新版")) {
    return "稳定版";
  }
  if (requestTitle.includes("IM版") || requestTitle.includes("IM版本") || requestTitle.includes("IM")) {
    return "IM版";
  }
  return "";
}

function buildTitle(payload) {
  const level = payload?.meta?.level || "";
  const liveVersion = inferLiveVersion(payload);
  const suffix = `${level}+${liveVersion}`.replace(/^\+|\+$/g, "");
  return suffix ? `直播值班（${suffix}）` : "直播值班";
}

function buildAttendees(payload, args) {
  if (args.notifyOnlyDuty) {
    return payload?.meta?.duty ? [payload.meta.duty] : [];
  }
  const merged = [
    ...(payload?.meta?.duty ? [payload.meta.duty] : []),
    ...(args.fixedAttendee ? [args.fixedAttendee] : []),
    ...(payload?.meta?.notify_targets || []),
    ...args.attendees,
  ];
  return [...new Set(merged.filter(Boolean))];
}

function buildDescription(payload) {
  const lines = [];
  if (payload?.meta?.level) {
    lines.push(`保障等级：${payload.meta.level}`);
  }
  if (payload?.meta?.duty) {
    lines.push(`值班后端：${payload.meta.duty}`);
  }
  lines.push("");
  lines.push("直播安排：");
  for (const item of payload.items || []) {
    lines.push(`${item.title}`);
    lines.push(`时间：${item.live_date || payload.meta.date} ${item.time}`);
    if (item.live_id) {
      lines.push(`直播ID：${item.live_id}`);
    }
    if (item.coverage != null) {
      lines.push(`覆盖人数：${item.coverage}`);
    }
    if (item.estimated != null) {
      lines.push(`预计人数：${item.estimated}`);
    }
    lines.push("");
  }
  return lines.join("\n").trim();
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const payload = readPayload(args);
  if (payload.errors && payload.errors.length) {
    throw new Error(`parsed payload contains errors: ${payload.errors.join("; ")}`);
  }
  if (!payload.items || !payload.items.length) {
    throw new Error("no live items found");
  }

  const firstItem = payload.items[0];
  const dateStr = firstItem.live_date || payload.meta.date;
  const timeStr = firstItem.time;
  if (!dateStr || !timeStr) {
    throw new Error("cannot build schedule without date and time");
  }

  const startAt = buildDateTime(dateStr, timeStr);
  const endAt = addMinutes(startAt, args.durationMinutes);

  const result = {
    title: buildTitle(payload),
    timezone: "Asia/Shanghai",
    start_at: formatLocal(startAt),
    end_at: formatLocal(endAt),
    reminder_minutes_before: args.reminderMinutesBefore,
    attendees: buildAttendees(payload, args),
    duty: payload.meta.duty || "",
    level: payload.meta.level || "",
    source_date: payload.meta.date || "",
    description: buildDescription(payload),
  };

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
