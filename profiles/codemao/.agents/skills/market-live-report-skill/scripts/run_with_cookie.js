#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const cp = require("child_process");
const { parseText, buildSheetRows, buildSheetMatrix } = require("./parse_live_report");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const { ensureMcporter, mcporterCall, safeJson } = require("./lib/mcporter");

const DEFAULT_CONFIG_PATH = path.resolve(__dirname, "../references/live-stream-api.local.json");
const EXAMPLE_CONFIG_PATH = path.resolve(
  __dirname,
  "../references/live-stream-api.local.example.json",
);
const SCHEDULER = path.resolve(__dirname, "./schedule_live_stats_collection.js");
const LOGIN_COOKIE = path.resolve(__dirname, "./login_live_stream_cookie.js");
const DEFAULT_TABLE_NODE_ID =
  "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr";
const DEFAULT_LOGIN_URL = "https://internal-account.codemao.cn/login";
const DEFAULT_RAW_CANDIDATES = [
  "input.txt",
  "references/today-live-report.local.txt",
  "references/live-report.local.txt",
];
const DATE_HEADERS = ["日期"];
const TITLE_HEADERS = ["事项", "直播标题", "标题"];
const TIME_HEADERS = ["时间", "开播时间"];
const ESTIMATED_COVERAGE_HEADERS = ["预计人数/覆盖人数"];
const ESTIMATED_HEADERS = ["预计人数", "预估参与", "预计参与"];
const COVERAGE_HEADERS = ["覆盖人数"];
const ACTUAL_HEADERS = ["实际人数"];
const DUTY_HEADERS = ["值班安排", "值班后端", "值班人员"];
const LIVE_ID_HEADERS = ["直播ID", "直播 Id", "Live ID", "live_id"];
const RESERVED_HEADERS = ["预约人数", "预约"];
const PRODUCT_ID_HEADERS = ["商品ID", "商品 Id", "product_id"];

function parseArgs(argv) {
  const args = {
    cookie: null,
    stdin: false,
    raw: [],
    date: todayInShanghai(),
    config: process.env.LIVE_STREAM_API_CONFIG || DEFAULT_CONFIG_PATH,
    tableNodeId: process.env.DINGTALK_TABLE_ID || process.env.DINGTALK_NODE_ID || DEFAULT_TABLE_NODE_ID,
    tableTarget: process.env.DINGTALK_MCP_TARGET || "钉钉表格",
    tableSheet: null,
    tableRange: "A1:Z200",
    validationLiveId: process.env.LIVE_STREAM_VALIDATION_LIVE_ID || null,
    cacheDir: null,
    milestones: null,
    dryRun: false,
    pretty: false,
    collectPast: false,
    pastGraceMinutes: 0,
    autoLoginCookie: true,
    loginUrl: DEFAULT_LOGIN_URL,
    loginTimeoutMs: 5 * 60 * 1000,
    loginPort: 9222,
    loginUserDataDir: null,
    chromePath: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--cookie":
        args.cookie = argv[++i];
        break;
      case "--stdin":
        args.stdin = true;
        break;
      case "--raw":
        args.raw.push(path.resolve(argv[++i]));
        break;
      case "--date":
        args.date = argv[++i];
        break;
      case "--config":
        args.config = path.resolve(argv[++i]);
        break;
      case "--table-node-id":
      case "--node-id":
        args.tableNodeId = argv[++i];
        break;
      case "--table-target":
        args.tableTarget = argv[++i];
        break;
      case "--table-sheet":
      case "--sheet-name":
        args.tableSheet = argv[++i];
        break;
      case "--table-range":
        args.tableRange = argv[++i];
        break;
      case "--validation-live-id":
        args.validationLiveId = argv[++i];
        break;
      case "--cache-dir":
        args.cacheDir = path.resolve(argv[++i]);
        break;
      case "--milestones":
        args.milestones = argv[++i];
        break;
      case "--collect-past":
        args.collectPast = true;
        break;
      case "--past-grace-minutes":
        args.pastGraceMinutes = Number(argv[++i]);
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
        if (!args.cookie && token.includes("=")) {
          args.cookie = token;
        } else {
          throw new Error(`unexpected argument: ${token}`);
        }
    }
  }

  if (!args.cookie && (args.stdin || !process.stdin.isTTY)) {
    args.cookie = fs.readFileSync(0, "utf8").trim();
  }

  return args;
}

function todayInShanghai() {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day}`;
}

function validateCookieShape(cookie) {
  if (!cookie) {
    throw new Error("empty cookie");
  }
  if (!cookie.includes("=")) {
    throw new Error("cookie should look like key=value; key2=value2");
  }
  if (/^cookie\s*:/i.test(cookie)) {
    throw new Error("paste only the Cookie header value, not the leading 'Cookie:' label");
  }
}

function loadConfigForSaving(configPath) {
  if (fs.existsSync(configPath)) {
    return JSON.parse(fs.readFileSync(configPath, "utf8"));
  }
  if (fs.existsSync(EXAMPLE_CONFIG_PATH)) {
    return JSON.parse(fs.readFileSync(EXAMPLE_CONFIG_PATH, "utf8"));
  }
  return {
    baseUrl: "https://lbk-mktadmin.codemao.cn",
    origin: "https://lbk-operational.codemao.cn",
    referer: "https://lbk-operational.codemao.cn/",
    cookie: "",
  };
}

function readSavedCookie(configPath) {
  if (!fs.existsSync(configPath)) {
    return "";
  }
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  return String(config.cookie || "").trim();
}

function saveCookie(configPath, cookie) {
  const config = loadConfigForSaving(configPath);
  config.cookie = cookie;
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

function parseNumber(value) {
  const cleaned = String(value == null ? "" : value).replace(/[^\d]/g, "");
  return cleaned ? Number(cleaned) : null;
}

function normalizeText(value) {
  return String(value == null ? "" : value).trim();
}

function normalizeHeader(value) {
  return normalizeText(value).replace(/\s+/g, "").toLowerCase();
}

function headerIndex(headers, candidates) {
  const normalized = headers.map(normalizeHeader);
  for (const candidate of candidates) {
    const index = normalized.indexOf(normalizeHeader(candidate));
    if (index >= 0) {
      return index;
    }
  }
  return -1;
}

function getCell(row, index) {
  return index >= 0 ? normalizeText(row[index]) : "";
}

function parseDisplayDate(value, fallbackYear) {
  const text = normalizeText(value);
  const full = text.match(/(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})/);
  if (full) {
    const [, year, month, day] = full;
    return `${year}-${String(Number(month)).padStart(2, "0")}-${String(Number(day)).padStart(2, "0")}`;
  }
  const short = text.match(/(\d{1,2})[-/.月](\d{1,2})/);
  if (short) {
    const [, month, day] = short;
    return `${fallbackYear}-${String(Number(month)).padStart(2, "0")}-${String(Number(day)).padStart(2, "0")}`;
  }
  return null;
}

function computeWeekday(dateStr) {
  const names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return names[new Date(`${dateStr}T00:00:00`).getDay()];
}

function stripTime(value) {
  const match = normalizeText(value).match(/(\d{1,2}:\d{2})/);
  return match ? match[1] : "";
}

function splitEstimatedCoverage(value) {
  const text = normalizeText(value);
  const [estimated, coverage] = text.split(/[\/／]/);
  return {
    estimated: parseNumber(estimated),
    coverage: parseNumber(coverage),
  };
}

function resolveSheetName(dateStr) {
  const date = new Date(`${dateStr}T00:00:00`);
  const weekStart = startOfWeekMonday(date);
  const month = weekStart.getMonth() + 1;
  const week = weekOfMonthByWeekStart(weekStart);
  return `M${month}W${week}`;
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

function existingRawFiles(args) {
  if (args.raw.length) {
    return args.raw.filter((filePath) => fs.existsSync(filePath));
  }

  const fromEnv = process.env.LIVE_REPORT_RAW ? [process.env.LIVE_REPORT_RAW] : [];
  return [...fromEnv, ...DEFAULT_RAW_CANDIDATES]
    .map((filePath) => path.resolve(filePath))
    .filter((filePath, index, list) => list.indexOf(filePath) === index)
    .filter((filePath) => fs.existsSync(filePath));
}

function buildParsedFromRows(rows, date, source) {
  const headerRowIndex = rows.findIndex((row) => {
    const headers = row.map(normalizeHeader);
    return DATE_HEADERS.some((header) => headers.includes(normalizeHeader(header))) &&
      TITLE_HEADERS.some((header) => headers.includes(normalizeHeader(header)));
  });
  if (headerRowIndex < 0) {
    return {
      parsed: null,
      tableSummary: {
        source,
        error: "missing header row with 日期 and 事项",
      },
    };
  }

  const headers = rows[headerRowIndex];
  const indexes = {
    date: headerIndex(headers, DATE_HEADERS),
    title: headerIndex(headers, TITLE_HEADERS),
    time: headerIndex(headers, TIME_HEADERS),
    estimatedCoverage: headerIndex(headers, ESTIMATED_COVERAGE_HEADERS),
    estimated: headerIndex(headers, ESTIMATED_HEADERS),
    coverage: headerIndex(headers, COVERAGE_HEADERS),
    actual: headerIndex(headers, ACTUAL_HEADERS),
    duty: headerIndex(headers, DUTY_HEADERS),
    liveId: headerIndex(headers, LIVE_ID_HEADERS),
    reserved: headerIndex(headers, RESERVED_HEADERS),
    productId: headerIndex(headers, PRODUCT_ID_HEADERS),
  };

  const year = date.slice(0, 4);
  const items = [];
  const warnings = [];
  let currentDate = null;
  let currentDuty = "";

  for (const row of rows.slice(headerRowIndex + 1)) {
    const rawDate = getCell(row, indexes.date);
    const parsedDate = rawDate ? parseDisplayDate(rawDate, year) : currentDate;
    if (parsedDate) {
      currentDate = parsedDate;
    }

    const rawDuty = getCell(row, indexes.duty);
    if (rawDuty) {
      currentDuty = rawDuty;
    }

    const title = getCell(row, indexes.title);
    if (!title || currentDate !== date) {
      continue;
    }

    const combined = splitEstimatedCoverage(getCell(row, indexes.estimatedCoverage));
    const item = {
      title,
      time: stripTime(getCell(row, indexes.time)),
      live_id: getCell(row, indexes.liveId),
      product_id: getCell(row, indexes.productId),
      reserved: parseNumber(getCell(row, indexes.reserved)),
      coverage: indexes.coverage >= 0 ? parseNumber(getCell(row, indexes.coverage)) : combined.coverage,
      estimated: indexes.estimated >= 0 ? parseNumber(getCell(row, indexes.estimated)) : combined.estimated,
      actual: parseNumber(getCell(row, indexes.actual)),
      live_date: date,
      duty: currentDuty,
    };

    if (!item.live_id) {
      warnings.push(`missing live_id for row title=${title}`);
    }
    items.push(item);
  }

  if (!items.length) {
    return {
      parsed: null,
      tableSummary: {
        source,
        sheet_header_row: headerRowIndex + 1,
        error: "no rows for requested date",
      },
    };
  }

  const meta = {
    date,
    weekday: computeWeekday(date),
    level: null,
    duty: items.find((item) => item.duty)?.duty || null,
    request_title: null,
    notify_targets: [],
    live_version: null,
  };
  const sheetRowsSparse = buildSheetRows(meta, items, true);
  const sheetRowsFull = buildSheetRows(meta, items, false);
  const missingRequired = [];
  items.forEach((item, index) => {
    if (!item.time) {
      missingRequired.push(`item ${index + 1} missing time`);
    }
    if (!item.live_id) {
      missingRequired.push(`item ${index + 1} missing live_id`);
    }
    if (item.coverage == null) {
      missingRequired.push(`item ${index + 1} missing coverage`);
    }
  });

  return {
    parsed: {
      meta,
      items,
      table_rows: [],
      sheet_rows_sparse: sheetRowsSparse,
      sheet_rows_full: sheetRowsFull,
      sheet_matrix_sparse: buildSheetMatrix(sheetRowsSparse),
      sheet_matrix_full: buildSheetMatrix(sheetRowsFull),
      warnings: [...new Set(warnings)],
      errors: [],
    },
    executable: missingRequired.length === 0,
    missingRequired,
    tableSummary: {
      source,
      sheet_header_row: headerRowIndex + 1,
      row_count: items.length,
      has_live_id_column: indexes.liveId >= 0,
    },
  };
}

function pickTodayReportFromDingTalk(args) {
  const sheetName = args.tableSheet || resolveSheetName(args.date);
  ensureMcporter();
  const output = safeJson(mcporterCall(args.tableTarget, "get_range", {
    nodeId: args.tableNodeId,
    sheetId: sheetName,
    range: args.tableRange,
  }));
  if (!output?.success) {
    throw new Error(`failed to read DingTalk sheet: ${output?.message || JSON.stringify(output)}`);
  }

  const rows = output.values || output.displayValues || [];
  const built = buildParsedFromRows(rows, args.date, {
    type: "dingtalk-table",
    node_id: args.tableNodeId,
    target: args.tableTarget,
    sheet_name: sheetName,
    range: args.tableRange,
  });

  return {
    file: built.parsed ? `${args.tableNodeId}#${sheetName}` : null,
    parsed: built.parsed,
    executable: built.executable,
    missingRequired: built.missingRequired || [],
    candidates: [built.tableSummary],
  };
}

function pickTodayReport(args) {
  if (!args.raw.length) {
    return pickTodayReportFromDingTalk(args);
  }

  const candidates = existingRawFiles(args);
  const parseResults = [];

  for (const filePath of candidates) {
    const parsed = parseText(fs.readFileSync(filePath, "utf8"), Number(args.date.slice(0, 4)));
    parseResults.push({
      file: filePath,
      errors: parsed.errors || [],
      date: parsed.meta?.date || null,
      item_count: parsed.items?.length || 0,
    });
    if (parsed.errors?.length) {
      continue;
    }

    const todayItems = (parsed.items || []).filter(
      (item) => (item.live_date || parsed.meta?.date) === args.date,
    );
    if (todayItems.length) {
      return {
        file: filePath,
        parsed: {
          ...parsed,
          meta: {
            ...parsed.meta,
            date: args.date,
          },
          items: todayItems,
        },
        executable: true,
        missingRequired: [],
        candidates: parseResults,
      };
    }
  }

  return {
    file: null,
    parsed: null,
    executable: false,
    missingRequired: [],
    candidates: parseResults,
  };
}

async function validateCookieByLive(cookie, configPath, liveId) {
  const config = loadConfig(configPath, { cookie });
  const stats = await fetchUserStatistics(liveId, config);
  return {
    live_id: String(liveId),
    totalCount: stats.totalCount,
    onlineCount: stats.onlineCount,
    reserveCount: stats.reserveCount,
  };
}

function runBrowserLoginCookie(args, validationLiveId) {
  const loginArgs = [
    LOGIN_COOKIE,
    "--config",
    args.config,
    "--login-url",
    args.loginUrl,
    "--browser-port",
    String(args.loginPort),
    "--login-timeout-ms",
    String(args.loginTimeoutMs),
  ];
  if (args.loginUserDataDir) {
    loginArgs.push("--browser-user-data-dir", args.loginUserDataDir);
  }
  if (args.chromePath) {
    loginArgs.push("--chrome-path", args.chromePath);
  }
  if (validationLiveId) {
    loginArgs.push("--validation-live-id", String(validationLiveId));
  }
  if (args.pretty) {
    loginArgs.push("--pretty");
  }
  return JSON.parse(cp.execFileSync(process.execPath, loginArgs, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
    env: process.env,
  }));
}

async function ensureCookie(args, validationLiveId) {
  let cookie = args.cookie || readSavedCookie(args.config);
  const source = args.cookie ? "argument" : cookie ? "config" : null;
  let validation = null;
  let validationError = null;

  if (cookie) {
    validateCookieShape(cookie);
  }

  if (cookie && validationLiveId) {
    try {
      validation = await validateCookieByLive(cookie, args.config, validationLiveId);
      return {
        cookie,
        source,
        refreshed: false,
        validation,
        login: null,
      };
    } catch (error) {
      validationError = error;
    }
  } else if (cookie) {
    return {
      cookie,
      source,
      refreshed: false,
      validation: {
        skipped: true,
        reason: "no validation live_id available",
      },
      login: null,
    };
  }

  if (!args.autoLoginCookie || args.dryRun) {
    if (validationError) {
      throw new Error(`cookie validation failed: ${validationError.message}`);
    }
    throw new Error(
      "missing live stream API cookie: pass --cookie, configure references/live-stream-api.local.json, or enable browser login",
    );
  }

  const login = runBrowserLoginCookie(args, validationLiveId);
  cookie = readSavedCookie(args.config);
  if (!cookie) {
    throw new Error("browser login completed but no cookie was saved");
  }
  validateCookieShape(cookie);

  if (validationLiveId) {
    validation = await validateCookieByLive(cookie, args.config, validationLiveId);
  } else {
    validation = {
      skipped: true,
      reason: "no validation live_id available",
    };
  }

  return {
    cookie,
    source: "browser-login",
    refreshed: true,
    validation,
    login,
    previous_validation_error: validationError ? validationError.message : null,
  };
}

function writeJsonTemp(prefix, value) {
  const filePath = path.join(
    os.tmpdir(),
    `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}.json`,
  );
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  return filePath;
}

function runScheduler(args, parsed) {
  const parsedPath = writeJsonTemp("today_live_report", parsed);
  try {
    const schedulerArgs = ["--parsed", parsedPath, "--cookie", args.cookie, "--config", args.config];
    if (args.cacheDir) {
      schedulerArgs.push("--cache-dir", args.cacheDir);
    }
    if (args.milestones) {
      schedulerArgs.push("--milestones", args.milestones);
    }
    if (args.collectPast) {
      schedulerArgs.push("--collect-past");
    }
    if (args.pastGraceMinutes) {
      schedulerArgs.push("--past-grace-minutes", String(args.pastGraceMinutes));
    }
    if (args.pretty) {
      schedulerArgs.push("--pretty");
    }
    return JSON.parse(cp.execFileSync(process.execPath, [SCHEDULER, ...schedulerArgs], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      env: process.env,
    }));
  } finally {
    try {
      fs.unlinkSync(parsedPath);
    } catch {}
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.cookie) {
    validateCookieShape(args.cookie);
  }

  const todayReport = pickTodayReport(args);
  const executableItems = (todayReport.parsed?.items || []).filter((item) => item.live_id);
  const validationLiveId = args.validationLiveId || executableItems[0]?.live_id || null;
  const result = {
    ok: true,
    date: args.date,
    config: args.config,
    cookie_source: null,
    cookie_refreshed: false,
    cookie_length: 0,
    today_report: todayReport.file,
    today_live_count: todayReport.parsed?.items?.length || 0,
    validation: null,
    saved: false,
    scheduler: null,
    raw_candidates: todayReport.candidates,
  };

  if (!todayReport.parsed) {
    const ensured = await ensureCookie(args, null);
    if (!args.dryRun) {
      saveCookie(args.config, ensured.cookie);
      result.saved = true;
    }
    result.cookie_source = ensured.source;
    result.cookie_refreshed = ensured.refreshed;
    result.cookie_length = ensured.cookie.length;
    result.validation = ensured.validation;
    result.status = "saved-unvalidated-no-live-today";
    process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
    return;
  }

  if (!validationLiveId || !todayReport.executable) {
    const ensured = await ensureCookie(args, null);
    if (!args.dryRun) {
      saveCookie(args.config, ensured.cookie);
      result.saved = true;
    }
    result.cookie_source = ensured.source;
    result.cookie_refreshed = ensured.refreshed;
    result.cookie_length = ensured.cookie.length;
    result.status = "saved-unvalidated-live-id-missing";
    result.validation = {
      skipped: true,
      reason: "today report rows do not include live_id; add 直播ID column or pass --validation-live-id",
    };
    result.missing_required = todayReport.missingRequired;
    process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
    return;
  }

  if (args.dryRun) {
    result.status = "dry-run-live-found";
    result.validation = {
      live_id: String(validationLiveId),
      skipped: true,
    };
    process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
    return;
  }

  const ensured = await ensureCookie(args, validationLiveId);
  args.cookie = ensured.cookie;
  result.cookie_source = ensured.source;
  result.cookie_refreshed = ensured.refreshed;
  result.cookie_length = ensured.cookie.length;
  result.validation = ensured.validation;
  if (ensured.previous_validation_error) {
    result.previous_validation_error = ensured.previous_validation_error;
  }
  if (ensured.login) {
    result.login = {
      saved: ensured.login.saved,
      cookie_length: ensured.login.cookie_length,
      cookie_names: ensured.login.cookie_names,
    };
  }
  saveCookie(args.config, ensured.cookie);
  result.saved = true;
  result.scheduler = runScheduler(args, todayReport.parsed);
  result.status = "validated-scheduler-started";
  process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
