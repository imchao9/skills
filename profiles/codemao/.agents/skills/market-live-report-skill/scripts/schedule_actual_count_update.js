#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { parseText } = require("./parse_live_report");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const {
  ensureMcporter,
  mcporterList,
  mcporterCall,
  safeJson,
  renderArgs,
} = require("./lib/mcporter");
const {
  DEFAULT_CONFIG_PATH,
  DEFAULT_LOGIN_URL,
  DEFAULT_PORT,
  DEFAULT_TIMEOUT_MS,
  ensureValidLiveStreamCookie,
} = require("./lib/live_stream_cookie");

const DEFAULT_ADAPTER = path.resolve(
  __dirname,
  "../references/dingtalk-spreadsheet-adapter.example.json",
);
const DEFAULT_NODE_CONFIG = path.resolve(__dirname, "../references/default-table-node.local.json");
const LIVE_ID_HEADERS = ["直播ID", "直播 Id", "Live ID", "live_id"];
const ACTUAL_HEADERS = ["实际人数"];

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    year: new Date().getFullYear(),
    adapter: DEFAULT_ADAPTER,
    target: process.env.DINGTALK_MCP_TARGET || "钉钉表格",
    nodeId: process.env.DINGTALK_TABLE_ID || process.env.DINGTALK_NODE_ID || null,
    sheetName: process.env.DINGTALK_SHEET_NAME || null,
    autoSheet: true,
    tableRange: "A1:G200",
    delayMinutes: 120,
    collectPast: false,
    pastGraceMinutes: 0,
    config: process.env.LIVE_STREAM_API_CONFIG || DEFAULT_CONFIG_PATH,
    cookie: null,
    autoLoginCookie: true,
    loginUrl: process.env.LIVE_STREAM_LOGIN_URL || DEFAULT_LOGIN_URL,
    loginTimeoutMs: Number(process.env.LIVE_STREAM_LOGIN_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
    loginPort: Number(process.env.LIVE_STREAM_LOGIN_DEBUG_PORT || DEFAULT_PORT),
    loginUserDataDir: null,
    chromePath: process.env.CHROME_PATH || null,
    dryRun: false,
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--raw":
        args.raw = argv[++i];
        break;
      case "--parsed":
        args.parsed = argv[++i];
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--adapter":
        args.adapter = argv[++i];
        break;
      case "--target":
      case "--table-target":
        args.target = argv[++i];
        break;
      case "--node-id":
      case "--table-id":
      case "--table-node-id":
        args.nodeId = argv[++i];
        break;
      case "--sheet-name":
        args.sheetName = argv[++i];
        args.autoSheet = false;
        break;
      case "--auto-sheet":
        args.autoSheet = true;
        break;
      case "--table-range":
        args.tableRange = argv[++i];
        break;
      case "--delay-minutes":
        args.delayMinutes = Number(argv[++i]);
        break;
      case "--collect-past":
        args.collectPast = true;
        break;
      case "--past-grace-minutes":
        args.pastGraceMinutes = Number(argv[++i]);
        break;
      case "--config":
        args.config = argv[++i];
        break;
      case "--cookie":
      case "--live-stream-cookie":
        args.cookie = argv[++i];
        break;
      case "--login-if-expired":
      case "--auto-login-cookie":
        args.autoLoginCookie = true;
        break;
      case "--no-login-if-expired":
      case "--no-auto-login-cookie":
        args.autoLoginCookie = false;
        break;
      case "--login-url":
        args.loginUrl = argv[++i];
        break;
      case "--login-timeout-ms":
        args.loginTimeoutMs = Number(argv[++i]);
        break;
      case "--browser-port":
      case "--login-port":
        args.loginPort = Number(argv[++i]);
        break;
      case "--browser-user-data-dir":
      case "--login-user-data-dir":
        args.loginUserDataDir = path.resolve(argv[++i]);
        break;
      case "--chrome-path":
        args.chromePath = argv[++i];
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--pretty":
        args.pretty = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw && !args.parsed) {
    throw new Error("pass --raw <file> or --parsed <file>");
  }
  if (!Number.isFinite(args.delayMinutes) || args.delayMinutes <= 0) {
    throw new Error("pass a positive --delay-minutes value");
  }
  if (!args.nodeId) {
    args.nodeId = readDefaultNodeId();
  }
  if (!args.nodeId) {
    throw new Error("missing node id or URL: pass --node-id/--table-id or set DINGTALK_TABLE_ID");
  }
  return args;
}

function readDefaultNodeId() {
  if (!fs.existsSync(DEFAULT_NODE_CONFIG)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(DEFAULT_NODE_CONFIG, "utf8")).node_id || null;
}

function readParsed(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  return parseText(fs.readFileSync(args.raw, "utf8"), args.year);
}

function loadAdapter(adapterPath) {
  return JSON.parse(fs.readFileSync(adapterPath, "utf8"));
}

function parseLocalDateTime(date, time) {
  const dateMatch = String(date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const timeMatch = String(time || "").match(/^(\d{1,2}):(\d{2})$/);
  if (!dateMatch || !timeMatch) {
    return null;
  }
  const [, year, month, day] = dateMatch;
  const [, hour, minute] = timeMatch;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0,
  );
}

function formatLocalDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join(" ");
}

function startOfWeekMonday(date) {
  const copy = new Date(date);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function firstMondayOfMonth(year, monthIndex) {
  const firstDay = new Date(year, monthIndex, 1);
  const day = firstDay.getDay();
  const offset = day === 0 ? 1 : day === 1 ? 0 : 8 - day;
  firstDay.setDate(firstDay.getDate() + offset);
  firstDay.setHours(0, 0, 0, 0);
  return firstDay;
}

function weekOfMonthByWeekStart(weekStart) {
  const firstMonday = firstMondayOfMonth(weekStart.getFullYear(), weekStart.getMonth());
  const diffDays = Math.round((weekStart - firstMonday) / 86400000);
  return Math.floor(diffDays / 7) + 1;
}

function resolveSheetName(args, parsed) {
  if (args.sheetName) {
    return args.sheetName;
  }
  if (!args.autoSheet) {
    return null;
  }
  const dateStr = parsed?.meta?.date;
  if (!dateStr) {
    throw new Error("cannot auto-select sheet without parsed meta.date");
  }
  const date = new Date(`${dateStr}T00:00:00`);
  const weekStart = startOfWeekMonday(date);
  const month = weekStart.getMonth() + 1;
  const week = weekOfMonthByWeekStart(weekStart);
  return `M${month}W${week}`;
}

function buildJobs(parsed, delayMinutes, now = new Date()) {
  const jobs = [];
  for (const item of parsed.items || []) {
    const liveDate = item.live_date || parsed.meta?.date;
    const startAt = parseLocalDateTime(liveDate, item.time);
    if (!startAt) {
      throw new Error(`cannot parse start time for live_id=${item.live_id || ""}`);
    }
    if (!item.live_id) {
      throw new Error(`missing live_id for title=${item.title || ""}`);
    }
    const runAt = new Date(startAt.getTime() + delayMinutes * 60 * 1000);
    jobs.push({
      date: liveDate,
      live_id: String(item.live_id),
      title: item.title,
      delay_minutes: delayMinutes,
      start_at: startAt.toISOString(),
      start_at_local: formatLocalDateTime(startAt),
      run_at: runAt.toISOString(),
      run_at_local: formatLocalDateTime(runAt),
      wait_ms: runAt.getTime() - now.getTime(),
    });
  }
  return jobs.sort((left, right) => new Date(left.run_at) - new Date(right.run_at));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeHeader(value) {
  return String(value || "").trim().replace(/\s+/g, "").toLowerCase();
}

function headerIndex(headers, candidates) {
  const normalizedCandidates = candidates.map(normalizeHeader);
  return headers.findIndex((header) => normalizedCandidates.includes(normalizeHeader(header)));
}

function normalizeLiveId(value) {
  const digits = String(value || "").replace(/[^\d]/g, "");
  return digits || String(value || "").trim();
}

function rowsFromRangeOutput(output) {
  return (
    output?.values ||
    output?.displayValues ||
    output?.data?.values ||
    output?.data?.displayValues ||
    []
  );
}

function parseStartCell(rangeAddress) {
  const match = String(rangeAddress || "").match(/^([A-Z]+)(\d+)/i);
  if (!match) {
    return { column: "A", row: 1 };
  }
  return { column: match[1].toUpperCase(), row: Number(match[2]) };
}

function columnIndexToName(index) {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function columnNameToIndex(name) {
  let value = 0;
  for (const char of String(name || "").toUpperCase()) {
    value = value * 26 + (char.charCodeAt(0) - 64);
  }
  return value - 1;
}

function cellAddress(rangeAddress, relativeColumnIndex, relativeRowIndex) {
  const start = parseStartCell(rangeAddress);
  const absoluteColumn = columnNameToIndex(start.column) + relativeColumnIndex;
  const absoluteRow = start.row + relativeRowIndex;
  const column = columnIndexToName(absoluteColumn);
  return `${column}${absoluteRow}:${column}${absoluteRow}`;
}

function findTargetCell(rows, rangeAddress, liveId) {
  const headerRowIndex = rows.findIndex((row) => {
    const liveIdIndex = headerIndex(row, LIVE_ID_HEADERS);
    const actualIndex = headerIndex(row, ACTUAL_HEADERS);
    return liveIdIndex >= 0 && actualIndex >= 0;
  });
  if (headerRowIndex < 0) {
    throw new Error("cannot find header row containing 直播ID and 实际人数");
  }

  const headers = rows[headerRowIndex];
  const liveIdIndex = headerIndex(headers, LIVE_ID_HEADERS);
  const actualIndex = headerIndex(headers, ACTUAL_HEADERS);
  const expected = normalizeLiveId(liveId);

  for (let rowIndex = headerRowIndex + 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex] || [];
    if (normalizeLiveId(row[liveIdIndex]) === expected) {
      return {
        header_row_index: headerRowIndex,
        row_index: rowIndex,
        live_id_column_index: liveIdIndex,
        actual_column_index: actualIndex,
        range_address: cellAddress(rangeAddress, actualIndex, rowIndex),
        current_value: row[actualIndex] ?? "",
      };
    }
  }

  throw new Error(`cannot find row for live_id=${liveId}`);
}

function ensureRequiredTools(adapter, schemaText) {
  const missing = [];
  for (const toolKey of ["get_range", "update_range"]) {
    const toolName = adapter.tools?.[toolKey]?.name;
    if (!toolName || !schemaText.includes(toolName)) {
      missing.push(toolName || toolKey);
    }
  }
  return missing;
}

function readSheetRows(args, adapter) {
  const getPayload = renderArgs(adapter.tools.get_range.args, {
    node_id: args.nodeId,
    sheet_id: args.sheetName,
    range_address: args.tableRange,
  });
  const output = safeJson(mcporterCall(args.target, adapter.tools.get_range.name, getPayload));
  if (output?.success === false) {
    throw new Error(`failed to read sheet range ${args.sheetName}!${args.tableRange}: ${output.message || output.errorMessage || "unknown error"}`);
  }
  const rows = rowsFromRangeOutput(output);
  if (!Array.isArray(rows) || !rows.length) {
    throw new Error(`failed to read sheet range ${args.sheetName}!${args.tableRange}`);
  }
  return { payload: getPayload, output, rows };
}

function updateActualCell(args, adapter, rangeAddress, totalCount) {
  const updatePayload = renderArgs(adapter.tools.update_range.args, {
    node_id: args.nodeId,
    sheet_id: args.sheetName,
    range_address: rangeAddress,
    values: [[String(totalCount)]],
  });
  const output = safeJson(mcporterCall(args.target, adapter.tools.update_range.name, updatePayload));
  if (output?.success === false) {
    throw new Error(`failed to update ${rangeAddress}: ${output.message || output.errorMessage || "unknown error"}`);
  }
  return { payload: updatePayload, output };
}

async function updateJob(job, args, adapter) {
  const config = loadConfig(args.config, { cookie: args.cookie });
  const stats = await fetchUserStatistics(job.live_id, config);
  const read = readSheetRows(args, adapter);
  const targetCell = findTargetCell(read.rows, args.tableRange, job.live_id);
  const write = updateActualCell(args, adapter, targetCell.range_address, stats.totalCount);
  return {
    ...job,
    status: "updated",
    stats: {
      totalCount: stats.totalCount,
      onlineCount: stats.onlineCount,
      reserveCount: stats.reserveCount,
    },
    target_cell: targetCell,
    read_action: {
      tool: adapter.tools.get_range.name,
      args: read.payload,
    },
    write_action: {
      tool: adapter.tools.update_range.name,
      args: write.payload,
      output: write.output,
    },
    updated_at: new Date().toISOString(),
  };
}

async function runScheduler(args, parsed, adapter, cookieStatus = null) {
  ensureMcporter();
  const schemaText = mcporterList(args.target);
  const missing = ensureRequiredTools(adapter, schemaText);
  if (missing.length) {
    throw new Error(`configured tools are missing from MCP schema: ${missing.join(", ")}`);
  }

  const jobs = buildJobs(parsed, args.delayMinutes);
  const results = [];

  for (const job of jobs) {
    const waitMs = new Date(job.run_at).getTime() - Date.now();
    const pastMs = Math.abs(Math.min(waitMs, 0));
    if (waitMs < 0 && !args.collectPast) {
      results.push({ ...job, status: "skipped-past" });
      continue;
    }
    if (
      waitMs < 0 &&
      args.pastGraceMinutes > 0 &&
      pastMs > args.pastGraceMinutes * 60 * 1000
    ) {
      results.push({ ...job, status: "skipped-past-grace" });
      continue;
    }

    if (waitMs > 0) {
      process.stderr.write(
        `waiting ${Math.ceil(waitMs / 1000)}s for live_id=${job.live_id} actual count\n`,
      );
      await sleep(waitMs);
    }

    try {
      const updated = await updateJob(job, args, adapter);
      results.push(updated);
      process.stderr.write(
        `updated live_id=${job.live_id} actual=${updated.stats.totalCount} at ${updated.target_cell.range_address}\n`,
      );
    } catch (error) {
      results.push({ ...job, status: "failed", error: error.message });
      process.stderr.write(`failed live_id=${job.live_id}: ${error.message}\n`);
    }
  }

  return {
    date: parsed.meta?.date || jobs[0]?.date || null,
    node_id: args.nodeId,
    sheet_name: args.sheetName,
    table_range: args.tableRange,
    delay_minutes: args.delayMinutes,
    cookie: cookieStatus ? {
      source: cookieStatus.source,
      refreshed: cookieStatus.refreshed,
      validation: cookieStatus.validation,
      previous_validation_error: cookieStatus.previous_validation_error || null,
    } : null,
    results,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readParsed(args);
  if (parsed.errors?.length) {
    throw new Error(parsed.errors.join("; "));
  }
  args.sheetName = resolveSheetName(args, parsed);
  const jobs = buildJobs(parsed, args.delayMinutes);

  const summary = {
    date: parsed.meta?.date || jobs[0]?.date || null,
    node_id: args.nodeId,
    sheet_name: args.sheetName,
    table_range: args.tableRange,
    delay_minutes: args.delayMinutes,
    source_column: "直播ID",
    target_column: "实际人数",
    value_from: "live-stream user-statistics data.totalCount",
    jobs,
  };

  if (args.dryRun) {
    process.stdout.write(`${JSON.stringify(summary, null, args.pretty ? 2 : 0)}\n`);
    return;
  }

  const adapter = loadAdapter(args.adapter);
  const cookieStatus = await ensureValidLiveStreamCookie(args, jobs[0]?.live_id || null);
  args.cookie = cookieStatus.cookie;
  const result = await runScheduler(args, parsed, adapter, cookieStatus);
  process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
