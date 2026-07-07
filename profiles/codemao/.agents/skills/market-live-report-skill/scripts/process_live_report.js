#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const cp = require("child_process");

const PARSER = path.resolve(__dirname, "./parse_live_report.js");
const SHEET_WRITER = path.resolve(__dirname, "./write_dingtalk_spreadsheet.js");
const SCHEDULE_BUILDER = path.resolve(__dirname, "./build_schedule_payload.js");
const SCHEDULE_CREATOR = path.resolve(__dirname, "./create_dingtalk_schedule.js");
const DUTY_DOC_PUBLISHER = path.resolve(__dirname, "./publish_duty_document.js");

function parseArgs(argv) {
  const args = {
    raw: null,
    year: new Date().getFullYear(),
    pretty: false,
    dryRun: false,
    skipSheet: false,
    skipCalendar: false,
    dutyDoc: false,
    dutyDocOutputDir: null,
    dutyDocDingtalk: false,
    dutyDocTarget: process.env.DINGTALK_DOC_MCP_TARGET || "钉钉文档",
    dutyDocStatsCacheDir: null,
    dutyDocFetchMissing: false,
    dutyDocIncludeResourceSection: false,
    dutyDocFormat: null,
    liveStreamConfig: null,
    liveStreamCookie: null,
    nodeId: process.env.DINGTALK_TABLE_ID || process.env.DINGTALK_NODE_ID || null,
    sheetName: process.env.DINGTALK_SHEET_NAME || null,
    autoSheet: true,
    tableTarget: process.env.DINGTALK_MCP_TARGET || "钉钉表格",
    calendarTarget: process.env.DINGTALK_CALENDAR_TARGET || "钉钉日历",
    writeMode: "append-rows",
    includeHeader: false,
    createSheet: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--raw":
        args.raw = argv[++i];
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--skip-sheet":
        args.skipSheet = true;
        break;
      case "--skip-calendar":
        args.skipCalendar = true;
        break;
      case "--duty-doc":
        args.dutyDoc = true;
        break;
      case "--duty-doc-out":
      case "--duty-doc-output-dir":
        args.dutyDocOutputDir = argv[++i];
        args.dutyDoc = true;
        break;
      case "--duty-doc-dingtalk":
        args.dutyDoc = true;
        args.dutyDocDingtalk = true;
        break;
      case "--duty-doc-target":
        args.dutyDocTarget = argv[++i];
        break;
      case "--duty-doc-stats-cache-dir":
        args.dutyDocStatsCacheDir = argv[++i];
        break;
      case "--duty-doc-fetch-missing":
        args.dutyDocFetchMissing = true;
        break;
      case "--duty-doc-include-resource-section":
        args.dutyDocIncludeResourceSection = true;
        break;
      case "--duty-doc-format":
        args.dutyDocFormat = argv[++i];
        args.dutyDoc = true;
        break;
      case "--duty-doc-markdown":
      case "--duty-doc-md":
        args.dutyDocFormat = "markdown";
        args.dutyDoc = true;
        break;
      case "--live-stream-config":
        args.liveStreamConfig = argv[++i];
        break;
      case "--cookie":
      case "--live-stream-cookie":
        args.liveStreamCookie = argv[++i];
        break;
      case "--node-id":
      case "--table-id":
        args.nodeId = argv[++i];
        break;
      case "--sheet-name":
        args.sheetName = argv[++i];
        args.autoSheet = false;
        break;
      case "--auto-sheet":
        args.autoSheet = true;
        break;
      case "--table-target":
        args.tableTarget = argv[++i];
        break;
      case "--calendar-target":
        args.calendarTarget = argv[++i];
        break;
      case "--write-mode":
        args.writeMode = argv[++i];
        break;
      case "--include-header":
        args.includeHeader = true;
        break;
      case "--create-sheet":
        args.createSheet = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw) {
    throw new Error("pass --raw <file>");
  }
  if (!args.skipSheet && !args.nodeId) {
    throw new Error("missing node id or URL: pass --node-id/--table-id or set DINGTALK_TABLE_ID");
  }
  return args;
}

function runNode(script, extraArgs) {
  return cp.execFileSync(process.execPath, [script, ...extraArgs], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    env: process.env,
  });
}

function safeJson(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function writeJsonTemp(prefix, value) {
  const filePath = path.join(
    os.tmpdir(),
    `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}.json`,
  );
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  return filePath;
}

function cleanup(files) {
  for (const filePath of files) {
    try {
      fs.unlinkSync(filePath);
    } catch {}
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const tempFiles = [];

  try {
    const parsed = safeJson(runNode(PARSER, ["--year", String(args.year), "--pretty", args.raw]));
    if (parsed.errors && parsed.errors.length) {
      throw new Error(`parsed payload contains errors: ${parsed.errors.join("; ")}`);
    }

    const parsedPath = writeJsonTemp("live_report_parsed", parsed);
    tempFiles.push(parsedPath);

    const schedulePayload = safeJson(
      runNode(SCHEDULE_BUILDER, ["--parsed", parsedPath, "--pretty"]),
    );
    const schedulePath = writeJsonTemp("live_report_schedule", schedulePayload);
    tempFiles.push(schedulePath);

    const result = {
      parsed: {
        meta: parsed.meta,
        warnings: parsed.warnings || [],
        preview_rows: parsed.sheet_rows_sparse || [],
      },
      sheet: null,
      schedule: null,
      duty_document: null,
    };

    if (args.dutyDoc) {
      const dutyArgs = ["--parsed", parsedPath];
      if (args.dutyDocOutputDir) {
        dutyArgs.push("--output-dir", args.dutyDocOutputDir);
      }
      if (args.dutyDocStatsCacheDir) {
        dutyArgs.push("--stats-cache-dir", args.dutyDocStatsCacheDir);
      }
      if (args.dutyDocFetchMissing) {
        dutyArgs.push("--fetch-missing");
      }
      if (args.dutyDocIncludeResourceSection) {
        dutyArgs.push("--include-resource-section");
      }
      if (args.dutyDocFormat) {
        dutyArgs.push("--format", args.dutyDocFormat);
      }
      if (args.liveStreamConfig) {
        dutyArgs.push("--config", args.liveStreamConfig);
      }
      if (args.liveStreamCookie) {
        dutyArgs.push("--cookie", args.liveStreamCookie);
      }
      if (args.dutyDocDingtalk) {
        dutyArgs.push("--dingtalk-doc", "--doc-target", args.dutyDocTarget);
      }
      if (args.dryRun) {
        dutyArgs.push("--dry-run");
      }
      if (args.pretty) {
        dutyArgs.push("--pretty");
      }
      result.duty_document = safeJson(runNode(DUTY_DOC_PUBLISHER, dutyArgs));
    }

    if (!args.skipSheet) {
      const sheetArgs = ["--parsed", parsedPath, "--target", args.tableTarget, "--node-id", args.nodeId, "--mode", args.writeMode];
      if (args.autoSheet) {
        sheetArgs.push("--auto-sheet");
      }
      if (args.sheetName) {
        sheetArgs.push("--sheet-name", args.sheetName);
      }
      if (args.includeHeader) {
        sheetArgs.push("--include-header");
      }
      if (args.createSheet) {
        sheetArgs.push("--create-sheet");
      }
      if (args.dryRun) {
        sheetArgs.push("--dry-run");
      }
      if (args.pretty) {
        sheetArgs.push("--pretty");
      }
      result.sheet = safeJson(runNode(SHEET_WRITER, sheetArgs));
    }

    if (!args.skipCalendar) {
      const calendarArgs = ["--payload", schedulePath, "--target", args.calendarTarget];
      if (args.dryRun) {
        calendarArgs.push("--dry-run");
      }
      if (args.pretty) {
        calendarArgs.push("--pretty");
      }
      result.schedule = safeJson(runNode(SCHEDULE_CREATOR, calendarArgs));
    }

    process.stdout.write(JSON.stringify(result, null, args.pretty ? 2 : 0));
    if (args.pretty) {
      process.stdout.write("\n");
    }
  } finally {
    cleanup(tempFiles);
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
}
