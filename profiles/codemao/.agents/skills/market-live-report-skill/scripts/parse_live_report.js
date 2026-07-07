#!/usr/bin/env node

const fs = require("fs");

const IGNORED_LINES = new Set([
  "申请事项",
  "事项详情",
  "当日直播日程如下：",
  "当日直播日程如下:",
]);

const GLOBAL_KEY_MAP = {
  日期: "date",
  星期: "weekday",
  保障等级: "level",
  值班后端: "duty",
  值班安排: "duty",
  值班人员: "duty",
  通知人: "notify_targets",
  提醒人: "notify_targets",
  相关人: "notify_targets",
  参会人: "notify_targets",
  直播版本: "live_version",
};

const ITEM_KEY_MAP = {
  开播时间: "time",
  时间: "time",
  直播ID: "live_id",
  商品ID: "product_id",
  覆盖人数: "coverage",
  预约人数: "reserved",
  预约: "reserved",
  预估参与: "estimated",
  预计参与: "estimated",
  预计人数: "estimated",
  预计上座人数: "estimated",
  实际人数: "actual",
};

const IGNORED_ITEM_KEYS = new Set(["班期ID", "抽奖礼品"]);

const WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function parseArgs(argv) {
  const args = {
    input: null,
    year: null,
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--pretty") {
      args.pretty = true;
      continue;
    }
    if (token === "--year") {
      const next = argv[i + 1];
      if (!next) {
        throw new Error("missing value for --year");
      }
      args.year = Number(next);
      i += 1;
      continue;
    }
    if (!args.input) {
      args.input = token;
      continue;
    }
    throw new Error(`unexpected argument: ${token}`);
  }

  return args;
}

function readText(inputPath) {
  if (inputPath) {
    return fs.readFileSync(inputPath, "utf8");
  }
  return fs.readFileSync(0, "utf8");
}

function normalizeLine(line) {
  return line.trim().replaceAll("：", ":");
}

function splitKeyValue(line) {
  const index = line.indexOf(":");
  if (index < 0) {
    return null;
  }
  const key = line.slice(0, index).trim();
  const value = line.slice(index + 1).trim();
  if (!key) {
    return null;
  }
  return [key, value];
}

function isSeparator(line) {
  return Boolean(line) && [...line].every((char) => char === "=");
}

function parseNumber(value) {
  if (value == null) {
    return null;
  }
  const cleaned = String(value).replace(/[^\d]/g, "");
  return cleaned ? Number(cleaned) : null;
}

function parseLiveDatetime(value, fallbackYear) {
  const text = String(value);

  const fullDateMatch = text.match(/(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})[日]?\s*(\d{2}:\d{2})/);
  if (fullDateMatch) {
    const [, year, month, day, time] = fullDateMatch;
    return {
      liveDate: `${String(year).padStart(4, "0")}-${String(Number(month)).padStart(2, "0")}-${String(Number(day)).padStart(2, "0")}`,
      time,
    };
  }

  const shortDateMatch = text.match(/(\d{1,2})-(\d{1,2})\s*(\d{2}:\d{2})/);
  if (shortDateMatch) {
    const [, month, day, time] = shortDateMatch;
    const year = fallbackYear || new Date().getFullYear();
    return {
      liveDate: `${String(year).padStart(4, "0")}-${String(Number(month)).padStart(2, "0")}-${String(Number(day)).padStart(2, "0")}`,
      time,
    };
  }

  const timeOnlyMatch = text.match(/(\d{2}:\d{2})/);
  if (timeOnlyMatch) {
    return {
      liveDate: null,
      time: timeOnlyMatch[1],
    };
  }

  return { liveDate: null, time: null };
}

function computeWeekday(dateStr) {
  const date = new Date(`${dateStr}T00:00:00`);
  const jsDay = date.getDay();
  const mondayBased = (jsDay + 6) % 7;
  return WEEKDAY_NAMES[mondayBased];
}

function formatDisplayDate(dateStr, weekday) {
  return `${weekday}${dateStr.slice(5)}`;
}

function buildEstimatedCoverage(estimated, coverage) {
  const estimatedText = estimated == null ? "" : String(estimated);
  const coverageText = coverage == null ? "" : String(coverage);
  return `${estimatedText}/${coverageText}`;
}

function buildSheetRows(meta, items, sparse) {
  const displayDate = meta.date && meta.weekday ? formatDisplayDate(meta.date, meta.weekday) : "";
  return items.map((item, index) => ({
    日期: sparse && index > 0 ? "" : displayDate,
    直播ID: item.live_id || "",
    事项: item.title || "",
    时间: item.time ? `（${item.time}）` : "",
    "预计人数/覆盖人数": buildEstimatedCoverage(item.estimated, item.coverage),
    实际人数: item.actual == null ? "" : String(item.actual),
    值班安排: sparse && index > 0 ? "" : meta.duty || "",
  }));
}

function buildSheetMatrix(rows) {
  return rows.map((row) => [
    row["日期"] || "",
    row["直播ID"] || "",
    row["事项"] || "",
    row["时间"] || "",
    row["预计人数/覆盖人数"] || "",
    row["实际人数"] || "",
    row["值班安排"] || "",
  ]);
}

function dedupePreserveOrder(values) {
  const seen = new Set();
  const ordered = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      ordered.push(value);
    }
  }
  return ordered;
}

function splitPeople(value) {
  return String(value)
    .split(/[，,、]/)
    .map((part) => part.trim().replace(/^@+/, ""))
    .filter(Boolean);
}

function finalizeItem(item, meta, fallbackYear, warnings) {
  const normalized = { ...item };
  const { liveDate, time } = parseLiveDatetime(item.time || "", fallbackYear);

  if (time) {
    normalized.time = time;
  }
  if (liveDate) {
    normalized.live_date = liveDate;
  }

  normalized.coverage = parseNumber(item.coverage);
  normalized.reserved = parseNumber(item.reserved);
  normalized.estimated = parseNumber(item.estimated);
  normalized.actual = parseNumber(item.actual);

  if (normalized.product_id === "") {
    normalized.product_id = null;
  }

  if (typeof normalized.duty === "string") {
    normalized.duty = normalized.duty.replace(/^@+/, "");
  }

  if (normalized.reserved == null) {
    warnings.push(`missing reserved for live_id=${normalized.live_id || ""}`);
  }
  if (normalized.estimated == null) {
    warnings.push(`missing estimated for live_id=${normalized.live_id || ""}`);
  }
  if (normalized.actual == null) {
    warnings.push(`missing actual for live_id=${normalized.live_id || ""}`);
  }
  if (!normalized.product_id) {
    warnings.push(`missing product_id for live_id=${normalized.live_id || ""}`);
  }

  if (!meta.date && normalized.live_date) {
    meta.date = normalized.live_date;
  }

  return normalized;
}

function parseText(text, fallbackYear) {
  const meta = {
    date: null,
    weekday: null,
    level: null,
    duty: null,
    request_title: null,
    notify_targets: [],
    live_version: null,
  };

  const items = [];
  const warnings = [];
  const errors = [];
  let currentItem = null;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = normalizeLine(rawLine);
    if (
      !line ||
      IGNORED_LINES.has(line) ||
      isSeparator(line) ||
      line.includes("配置信息如下")
    ) {
      continue;
    }

    const inlineTitleTime = line.match(/^(【.+?】)\s*时间:(.+)$/);
    if (inlineTitleTime) {
      if (
        currentItem &&
        ["time", "live_id", "coverage", "estimated", "actual", "product_id"].some(
          (field) => Object.prototype.hasOwnProperty.call(currentItem, field),
        )
      ) {
        items.push(finalizeItem(currentItem, meta, fallbackYear, warnings));
      }
      currentItem = {
        title: inlineTitleTime[1],
        time: inlineTitleTime[2].trim(),
      };
      continue;
    }

    const pair = splitKeyValue(line);
    if (pair) {
      const [key, value] = pair;
      if (GLOBAL_KEY_MAP[key]) {
        const mappedKey = GLOBAL_KEY_MAP[key];
        if (mappedKey === "notify_targets") {
          meta.notify_targets = dedupePreserveOrder([
            ...(meta.notify_targets || []),
            ...splitPeople(value),
          ]);
        } else {
          const normalizedValue =
            mappedKey === "duty" ? value.replace(/^@+/, "") : value;
          meta[mappedKey] = normalizedValue || null;
        }
        continue;
      }
      if (ITEM_KEY_MAP[key]) {
        if (!currentItem) {
          currentItem = { title: null };
        }
        currentItem[ITEM_KEY_MAP[key]] = value;
        continue;
      }
      if (IGNORED_ITEM_KEYS.has(key)) {
        if (!currentItem) {
          currentItem = { title: null };
        }
        continue;
      }
    }

    if (currentItem && currentItem.title === line) {
      continue;
    }

    if (!meta.request_title && line.includes("报备")) {
      meta.request_title = line;
      continue;
    }

    if (
      currentItem &&
      ["time", "live_id", "coverage", "estimated", "actual", "product_id"].some(
        (field) => Object.prototype.hasOwnProperty.call(currentItem, field),
      )
    ) {
      if (
        currentItem.time &&
        !currentItem.live_id &&
        !currentItem.coverage &&
        !currentItem.estimated &&
        !currentItem.actual &&
        !currentItem.product_id
      ) {
        currentItem.title = line;
        continue;
      }
      items.push(finalizeItem(currentItem, meta, fallbackYear, warnings));
    }

    currentItem = { title: line };
  }

  if (currentItem) {
    items.push(finalizeItem(currentItem, meta, fallbackYear, warnings));
  }

  if (meta.date && !meta.weekday) {
    meta.weekday = computeWeekday(meta.date);
    warnings.push("weekday omitted and auto-computed from date");
  }

  if (!meta.date) {
    errors.push("cannot determine final date");
  }
  if (!meta.weekday && meta.date) {
    errors.push("cannot determine weekday");
  }
  if (!items.length) {
    errors.push("no live items found");
  }

  items.forEach((item, index) => {
    const number = index + 1;
    if (!item.title) {
      errors.push(`item ${number} missing title`);
    }
    if (!item.time) {
      errors.push(`item ${number} missing time`);
    }
    if (!item.live_id) {
      errors.push(`item ${number} missing live_id`);
    }
    if (item.coverage == null) {
      errors.push(`item ${number} missing coverage`);
    }
  });

  const tableRows = [];
  let sheetRowsSparse = [];
  let sheetRowsFull = [];
  if (!errors.length && meta.date && meta.weekday) {
    const displayDate = formatDisplayDate(meta.date, meta.weekday);
    for (const item of items) {
      tableRows.push({
        日期: displayDate,
        事项: item.title,
        时间: item.time ? `（${item.time}）` : "",
        "预计人数/覆盖人数": buildEstimatedCoverage(item.estimated, item.coverage),
        实际人数: item.actual == null ? "" : String(item.actual),
        值班安排: meta.duty || "",
        直播ID: item.live_id || "",
        商品ID: item.product_id || "",
        保障等级: meta.level || "",
      });
    }
    sheetRowsSparse = buildSheetRows(meta, items, true);
    sheetRowsFull = buildSheetRows(meta, items, false);
  }

  return {
    meta,
    items,
    table_rows: tableRows,
    sheet_rows_sparse: sheetRowsSparse,
    sheet_rows_full: sheetRowsFull,
    sheet_matrix_sparse: buildSheetMatrix(sheetRowsSparse),
    sheet_matrix_full: buildSheetMatrix(sheetRowsFull),
    warnings: dedupePreserveOrder(warnings),
    errors: dedupePreserveOrder(errors),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const text = readText(args.input);

  let payload;
  if (!text.trim()) {
    payload = {
      meta: { date: null, weekday: null, level: null, duty: null },
      items: [],
      table_rows: [],
      sheet_rows_sparse: [],
      sheet_rows_full: [],
      sheet_matrix_sparse: [],
      sheet_matrix_full: [],
      warnings: [],
      errors: ["empty input"],
    };
  } else {
    payload = parseText(text, args.year);
  }

  const output = JSON.stringify(payload, null, args.pretty ? 2 : 0);
  process.stdout.write(output);
  if (args.pretty) {
    process.stdout.write("\n");
  }
  process.exit(payload.errors.length ? 1 : 0);
}

if (require.main === module) {
  main();
}

module.exports = {
  parseText,
  buildSheetRows,
  buildSheetMatrix,
};
