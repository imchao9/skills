#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const cp = require("child_process");
const { parseText } = require("./parse_live_report");

const DEFAULT_ADAPTER = path.resolve(
  __dirname,
  "../references/dingtalk-spreadsheet-adapter.example.json",
);

const HEADER_ROW = ["日期", "直播ID", "事项", "时间", "预计人数/覆盖人数", "实际人数", "值班安排"];
const DEFAULT_STYLE_TEMPLATE_SHEET = "M6W5";
const DEFAULT_STYLE_DATA_RANGE = "A2:G5";

function parseArgs(argv) {
  const args = {
    adapter: DEFAULT_ADAPTER,
    parsed: null,
    raw: null,
    pretty: false,
    year: new Date().getFullYear(),
    target: process.env.DINGTALK_MCP_TARGET || null,
    nodeId: process.env.DINGTALK_TABLE_ID || process.env.DINGTALK_NODE_ID || null,
    sheetName: process.env.DINGTALK_SHEET_NAME || null,
    autoSheet: false,
    createSheet: false,
    startRow: 2,
    mode: "append-rows",
    dryRun: false,
    includeHeader: false,
    copyTemplateStyle: true,
    styleTemplateSheet: process.env.DINGTALK_STYLE_TEMPLATE_SHEET || DEFAULT_STYLE_TEMPLATE_SHEET,
    styleTemplateRange: "A1:G200",
    styleDataRange: process.env.DINGTALK_STYLE_DATA_RANGE || DEFAULT_STYLE_DATA_RANGE,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--adapter":
        args.adapter = argv[++i];
        break;
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
      case "--target":
        args.target = argv[++i];
        break;
      case "--table-id":
      case "--node-id":
        args.nodeId = argv[++i];
        break;
      case "--sheet-name":
        args.sheetName = argv[++i];
        break;
      case "--auto-sheet":
        args.autoSheet = true;
        break;
      case "--create-sheet":
        args.createSheet = true;
        break;
      case "--start-row":
        args.startRow = Number(argv[++i]);
        break;
      case "--mode":
        args.mode = argv[++i];
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--include-header":
        args.includeHeader = true;
        break;
      case "--style-template-sheet":
        args.styleTemplateSheet = argv[++i];
        args.copyTemplateStyle = true;
        break;
      case "--style-template-range":
        args.styleTemplateRange = argv[++i];
        break;
      case "--style-data-range":
        args.styleDataRange = argv[++i];
        break;
      case "--no-copy-template-style":
        args.copyTemplateStyle = false;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.parsed && !args.raw) {
    throw new Error("pass --parsed <file> or --raw <file>");
  }
  if (!args.sheetName && !args.autoSheet) {
    throw new Error("missing sheet name: pass --sheet-name, --auto-sheet, or set DINGTALK_SHEET_NAME");
  }
  if (!args.nodeId) {
    throw new Error("missing node id or URL: pass --node-id/--table-id or set DINGTALK_TABLE_ID");
  }

  return args;
}

function loadAdapter(adapterPath) {
  return JSON.parse(fs.readFileSync(adapterPath, "utf8"));
}

function readPayload(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  const text = fs.readFileSync(args.raw, "utf8");
  return parseText(text, args.year);
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

function safeJson(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function isSheetNotFound(output) {
  const code = output?.errorCode || null;
  const message = `${output?.errorMessage || ""} ${output?.message || ""}`.toLowerCase();
  return code === "invalidRequest.resource.notFound" || message.includes("resource was not found");
}

function ensureRequiredTools(adapter, schemaText, createSheet, mode, copyTemplateStyle, styleTemplateSheet) {
  const required = [];
  if (createSheet) {
    required.push(adapter.tools.create_sheet.name);
  }
  if (mode === "append-rows") {
    required.push(adapter.tools.append_rows.name);
  } else if (mode === "update-range") {
    required.push(adapter.tools.update_range.name);
  } else {
    throw new Error(`unsupported mode: ${mode}`);
  }
  if (adapter.tools.merge_cells) {
    required.push(adapter.tools.merge_cells.name);
    if (mode === "append-rows") {
      for (const toolKey of ["get_range", "update_range", "unmerge_range"]) {
        if (adapter.tools[toolKey]) {
          required.push(adapter.tools[toolKey].name);
        }
      }
    }
  }
  if (createSheet && copyTemplateStyle && adapter.tools.copy_range) {
    required.push(adapter.tools.copy_range.name);
    if (!styleTemplateSheet && adapter.tools.get_all_sheets) {
      required.push(adapter.tools.get_all_sheets.name);
    }
  }
  return required.filter((toolName) => !schemaText.includes(toolName));
}

function hasTool(adapter, schemaText, toolKey) {
  const tool = adapter.tools[toolKey];
  return Boolean(tool?.name && schemaText.includes(tool.name));
}

function parseA1Range(a1Range) {
  const match = String(a1Range || "").match(/^([A-Z]+)(\d+):([A-Z]+)(\d+)$/i);
  if (!match) {
    return null;
  }
  return {
    startColumn: match[1].toUpperCase(),
    startRow: Number(match[2]),
    endColumn: match[3].toUpperCase(),
    endRow: Number(match[4]),
  };
}

function buildValues(payload, includeHeader) {
  const values = payload.sheet_matrix_sparse || [];
  return includeHeader ? [HEADER_ROW, ...values] : values;
}

function resolveSheetName(args, payload) {
  if (args.sheetName) {
    return args.sheetName;
  }
  if (!args.autoSheet) {
    return null;
  }
  const dateStr = payload?.meta?.date;
  if (!dateStr) {
    throw new Error("cannot auto-select sheet without parsed meta.date");
  }
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

function parseWeeklySheetName(name) {
  const match = String(name || "").match(/^M(\d+)W(\d+)$/i);
  if (!match) {
    return null;
  }
  return {
    month: Number(match[1]),
    week: Number(match[2]),
  };
}

function compareWeeklySheetNames(leftName, rightName) {
  const left = parseWeeklySheetName(leftName);
  const right = parseWeeklySheetName(rightName);
  if (!left && !right) {
    return String(leftName || "").localeCompare(String(rightName || ""));
  }
  if (!left) {
    return -1;
  }
  if (!right) {
    return 1;
  }
  return left.month - right.month || left.week - right.week;
}

function listSheets(args, adapter, result, purpose = "list-sheets") {
  const listPayload = renderArgs(adapter.tools.get_all_sheets.args, {
    node_id: args.nodeId,
  });
  const output = safeJson(mcporterCall(args.target, adapter.tools.get_all_sheets.name, listPayload));
  result.actions.push({
    tool: adapter.tools.get_all_sheets.name,
    args: listPayload,
    output,
    purpose,
  });
  return Array.isArray(output?.sheets) ? output.sheets : [];
}

function selectStyleTemplateSheet(args, sheets) {
  if (args.styleTemplateSheet) {
    return args.styleTemplateSheet;
  }

  const candidates = sheets
    .map((sheet) => sheet.name || sheet.sheetId)
    .filter((name) => name && name !== args.sheetName && parseWeeklySheetName(name))
    .sort(compareWeeklySheetNames);
  return candidates[candidates.length - 1] || null;
}

function applyTemplateStyle(args, adapter, schemaText, result) {
  if (
    !args.copyTemplateStyle ||
    !hasTool(adapter, schemaText, "copy_range") ||
    (!args.styleTemplateSheet && !hasTool(adapter, schemaText, "get_all_sheets"))
  ) {
    return null;
  }

  const sheets = args.styleTemplateSheet ? [] : listSheets(args, adapter, result, "select-style-template-sheet");
  const sourceSheetId = selectStyleTemplateSheet(args, sheets);
  if (!sourceSheetId) {
    result.style_template = {
      copied: false,
      reason: "no weekly template sheet found",
    };
    return null;
  }

  const copyPayload = renderArgs(adapter.tools.copy_range.args, {
    node_id: args.nodeId,
    source_sheet_id: sourceSheetId,
    target_sheet_id: args.sheetName,
    source_range: args.styleTemplateRange,
    destination_range: "A1",
    paste_type: "formats",
  });
  const output = safeJson(mcporterCall(args.target, adapter.tools.copy_range.name, copyPayload));
  result.actions.push({
    tool: adapter.tools.copy_range.name,
    args: copyPayload,
    output,
    purpose: "copy-template-style",
  });
  result.style_template = {
    copied: Boolean(output?.success),
    source_sheet_id: sourceSheetId,
    source_range: args.styleTemplateRange,
    target_sheet_id: args.sheetName,
    destination_range: "A1",
  };
  return result.style_template;
}

function applyRepeatedDataRowStyle(args, adapter, schemaText, result, dataStartRow, dataRowCount) {
  if (
    !args.copyTemplateStyle ||
    !hasTool(adapter, schemaText, "copy_range") ||
    !args.styleTemplateSheet ||
    !dataStartRow ||
    dataRowCount <= 0
  ) {
    return null;
  }

  const parsedRange = parseA1Range(args.styleDataRange);
  if (!parsedRange) {
    result.data_row_style = {
      copied: false,
      reason: `invalid style data range: ${args.styleDataRange}`,
    };
    return null;
  }

  const templateRowCount = parsedRange.endRow - parsedRange.startRow + 1;
  const firstUncoveredRowOffset = templateRowCount;
  if (dataRowCount <= firstUncoveredRowOffset) {
    result.data_row_style = {
      copied: false,
      reason: "data rows fit template data style range",
      source_range: args.styleDataRange,
      covered_rows: dataRowCount,
    };
    return result.data_row_style;
  }

  const copies = [];
  for (let offset = firstUncoveredRowOffset; offset < dataRowCount; offset += templateRowCount) {
    const destinationRow = dataStartRow + offset;
    const rowsToCover = Math.min(templateRowCount, dataRowCount - offset);
    const sourceEndRow = parsedRange.startRow + rowsToCover - 1;
    const sourceRange = `${parsedRange.startColumn}${parsedRange.startRow}:${parsedRange.endColumn}${sourceEndRow}`;
    const copyPayload = renderArgs(adapter.tools.copy_range.args, {
      node_id: args.nodeId,
      source_sheet_id: args.styleTemplateSheet,
      target_sheet_id: args.sheetName,
      source_range: sourceRange,
      destination_range: `${parsedRange.startColumn}${destinationRow}`,
      paste_type: "formats",
    });
    const output = safeJson(mcporterCall(args.target, adapter.tools.copy_range.name, copyPayload));
    result.actions.push({
      tool: adapter.tools.copy_range.name,
      args: copyPayload,
      output,
      purpose: "copy-repeated-data-row-style",
    });
    copies.push({
      source_range: sourceRange,
      destination_range: `${parsedRange.startColumn}${destinationRow}`,
      copied: Boolean(output?.success),
    });
  }

  result.data_row_style = {
    copied: copies.some((copy) => copy.copied),
    source_sheet_id: args.styleTemplateSheet,
    source_range: args.styleDataRange,
    target_sheet_id: args.sheetName,
    data_start_row: dataStartRow,
    data_row_count: dataRowCount,
    copies,
  };
  return result.data_row_style;
}

function unmergeRanges(args, adapter, schemaText, result, ranges, purpose) {
  if (!ranges.length || !hasTool(adapter, schemaText, "unmerge_range")) {
    return;
  }

  for (const rangeAddress of ranges) {
    const unmergePayload = renderArgs(adapter.tools.unmerge_range.args, {
      node_id: args.nodeId,
      sheet_id: args.sheetName,
      range_address: rangeAddress,
    });
    result.actions.push({
      tool: adapter.tools.unmerge_range.name,
      args: unmergePayload,
      output: safeJson(mcporterCall(args.target, adapter.tools.unmerge_range.name, unmergePayload)),
      purpose,
    });
  }
}

function buildContext(args, values) {
  const endRow = args.startRow + values.length - 1;
  return {
    node_id: args.nodeId,
    sheet_name: args.sheetName,
    sheet_id: args.sheetName,
    start_row: args.startRow,
    range_address: `A${args.startRow}:G${endRow}`,
    values,
  };
}

function buildMergeRanges(args, payload, values, baseStartRow = null) {
  const sourceRows = args.includeHeader ? payload.sheet_rows_sparse || [] : payload.sheet_rows_sparse || [];
  if (sourceRows.length <= 1) {
    return [];
  }

  const effectiveStartRow = baseStartRow ?? args.startRow;
  const dataStartRow = args.includeHeader ? effectiveStartRow + 1 : effectiveStartRow;
  const dataEndRow = dataStartRow + sourceRows.length - 1;

  return [
    `A${dataStartRow}:A${dataEndRow}`,
    `G${dataStartRow}:G${dataEndRow}`,
  ];
}

function buildTemplateDataMergeRanges(args, dataStartRow) {
  const parsedRange = parseA1Range(args.styleDataRange);
  if (!parsedRange || !dataStartRow) {
    return [];
  }
  const templateRowCount = parsedRange.endRow - parsedRange.startRow + 1;
  const endRow = dataStartRow + templateRowCount - 1;
  return [`A${dataStartRow}:A${endRow}`, `G${dataStartRow}:G${endRow}`];
}

function buildRepeatedDataStyleMergeRanges(args, dataStartRow, dataRowCount) {
  const parsedRange = parseA1Range(args.styleDataRange);
  if (!parsedRange || !dataStartRow || dataRowCount <= 0) {
    return [];
  }

  const templateRowCount = parsedRange.endRow - parsedRange.startRow + 1;
  const ranges = [];
  for (let offset = templateRowCount; offset < dataRowCount; offset += templateRowCount) {
    const startRow = dataStartRow + offset;
    const rowsToCover = Math.min(templateRowCount, dataRowCount - offset);
    const endRow = startRow + rowsToCover - 1;
    if (startRow < endRow) {
      ranges.push(`A${startRow}:A${endRow}`, `G${startRow}:G${endRow}`);
    }
  }
  return ranges;
}

function extractStartRowFromA1(a1Notation) {
  if (!a1Notation) {
    return null;
  }
  const match = String(a1Notation).match(/[A-Z]+(\d+):[A-Z]+(\d+)/i);
  if (!match) {
    return null;
  }
  return Number(match[1]);
}

function extractRowBoundsFromA1(a1Notation) {
  if (!a1Notation) {
    return null;
  }
  const match = String(a1Notation).match(/[A-Z]+(\d+):[A-Z]+(\d+)/i);
  if (!match) {
    return null;
  }
  return {
    startRow: Number(match[1]),
    endRow: Number(match[2]),
  };
}

function firstRowValues(rangeOutput) {
  const rows = rangeOutput?.values || rangeOutput?.displayValues || [];
  return Array.isArray(rows) && Array.isArray(rows[0]) ? rows[0].map((value) => String(value || "").trim()) : [];
}

function normalizeCell(value) {
  return String(value || "").trim();
}

function findContiguousDateBlock(rangeOutput, dateLabel, appendedStartRow, appendedEndRow) {
  const rows = rangeOutput?.values || rangeOutput?.displayValues || [];
  if (!Array.isArray(rows) || !dateLabel || !appendedStartRow || !appendedEndRow) {
    return null;
  }

  let startRow = appendedStartRow;
  for (let rowNumber = appendedStartRow; rowNumber >= 2; rowNumber -= 1) {
    const row = rows[rowNumber - 1] || [];
    const dateValue = normalizeCell(row[0]);
    if (!dateValue) {
      continue;
    }
    if (dateValue !== dateLabel) {
      break;
    }
    startRow = rowNumber;
  }

  let endRow = appendedEndRow;
  for (let rowNumber = appendedEndRow + 1; rowNumber <= rows.length; rowNumber += 1) {
    const row = rows[rowNumber - 1] || [];
    const dateValue = normalizeCell(row[0]);
    if (!dateValue) {
      const hasLiveId = normalizeCell(row[1]);
      if (hasLiveId) {
        endRow = rowNumber;
      }
      continue;
    }
    if (dateValue === dateLabel) {
      endRow = rowNumber;
      continue;
    }
    break;
  }

  return startRow < endRow ? { startRow, endRow } : null;
}

function maybeConsolidateDateBlock(args, adapter, result, payload, appendedRange) {
  if (
    !adapter.tools.merge_cells ||
    !adapter.tools.unmerge_range ||
    !adapter.tools.get_range ||
    !adapter.tools.update_range ||
    !appendedRange
  ) {
    return null;
  }

  const dateLabel = payload.sheet_rows_sparse?.[0]?.日期;
  if (!dateLabel) {
    return null;
  }

  const getPayload = renderArgs(adapter.tools.get_range.args, {
    node_id: args.nodeId,
    sheet_id: args.sheetName,
    range_address: `A1:G${appendedRange.endRow}`,
  });
  const getOutput = safeJson(mcporterCall(args.target, adapter.tools.get_range.name, getPayload));
  result.actions.push({
    tool: adapter.tools.get_range.name,
    args: getPayload,
    output: getOutput,
    purpose: "consolidate-date-block",
  });
  if (!getOutput?.success) {
    return null;
  }

  const block = findContiguousDateBlock(
    getOutput,
    dateLabel,
    appendedRange.startRow,
    appendedRange.endRow,
  );
  if (!block) {
    return null;
  }

  const fullRanges = [`A${block.startRow}:A${block.endRow}`, `G${block.startRow}:G${block.endRow}`];
  for (const rangeAddress of fullRanges) {
    const unmergePayload = renderArgs(adapter.tools.unmerge_range.args, {
      node_id: args.nodeId,
      sheet_id: args.sheetName,
      range_address: rangeAddress,
    });
    result.actions.push({
      tool: adapter.tools.unmerge_range.name,
      args: unmergePayload,
      output: safeJson(mcporterCall(args.target, adapter.tools.unmerge_range.name, unmergePayload)),
    });
  }

  const emptyValues = Array.from({ length: block.endRow - block.startRow }, () => [""]);
  for (const column of ["A", "G"]) {
    const rangeAddress = `${column}${block.startRow + 1}:${column}${block.endRow}`;
    const updatePayload = renderArgs(adapter.tools.update_range.args, {
      node_id: args.nodeId,
      sheet_id: args.sheetName,
      range_address: rangeAddress,
      values: emptyValues,
    });
    result.actions.push({
      tool: adapter.tools.update_range.name,
      args: updatePayload,
      output: safeJson(mcporterCall(args.target, adapter.tools.update_range.name, updatePayload)),
    });
  }

  return fullRanges;
}

function ensureLiveIdColumn(args, adapter, schemaText, result) {
  if (
    args.createSheet ||
    !hasTool(adapter, schemaText, "get_range") ||
    !hasTool(adapter, schemaText, "insert_dimension") ||
    !hasTool(adapter, schemaText, "update_range")
  ) {
    return;
  }

  const headerContext = {
    node_id: args.nodeId,
    sheet_id: args.sheetName,
    range_address: "A1:G1",
    position: "B",
    dimension: "COLUMNS",
    length: 1,
    values: [["直播ID"]],
  };
  const getPayload = renderArgs(adapter.tools.get_range.args, headerContext);
  const getOutput = safeJson(mcporterCall(args.target, adapter.tools.get_range.name, getPayload));
  result.actions.push({
    tool: adapter.tools.get_range.name,
    args: getPayload,
    output: getOutput,
  });

  if (!getOutput?.success) {
    return;
  }

  const header = firstRowValues(getOutput);
  if (header[1] === "直播ID") {
    return;
  }
  if (header[0] !== "日期" || !header.includes("事项")) {
    return;
  }

  const insertPayload = renderArgs(adapter.tools.insert_dimension.args, headerContext);
  result.actions.push({
    tool: adapter.tools.insert_dimension.name,
    args: insertPayload,
    output: safeJson(mcporterCall(args.target, adapter.tools.insert_dimension.name, insertPayload)),
  });

  const updatePayload = renderArgs(adapter.tools.update_range.args, {
    ...headerContext,
    range_address: "B1:B1",
  });
  result.actions.push({
    tool: adapter.tools.update_range.name,
    args: updatePayload,
    output: safeJson(mcporterCall(args.target, adapter.tools.update_range.name, updatePayload)),
  });
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const adapter = loadAdapter(args.adapter);
  const payload = readPayload(args);

  if (payload.errors && payload.errors.length) {
    throw new Error(`parsed payload contains errors: ${payload.errors.join("; ")}`);
  }

  args.sheetName = resolveSheetName(args, payload);

  const values = buildValues(payload, args.includeHeader);
  if (!values.length) {
    throw new Error("parsed payload does not contain spreadsheet values");
  }

  const context = buildContext(args, values);
  let mergeRanges = buildMergeRanges(args, payload, values);
  const summary = {
    adapter: path.resolve(args.adapter),
    target: args.target,
    node_id: args.nodeId,
    sheet_name: args.sheetName,
    auto_sheet: args.autoSheet,
    mode: args.mode,
    create_sheet: args.createSheet,
    include_header: args.includeHeader,
    copy_template_style: args.copyTemplateStyle,
    style_template_sheet: args.styleTemplateSheet,
    style_template_range: args.styleTemplateRange,
    style_data_range: args.styleDataRange,
    row_count: values.length,
    range_address: context.range_address,
    merge_ranges: mergeRanges,
    preview_rows: payload.sheet_rows_sparse,
    write_values: values,
  };

  if (args.dryRun) {
    process.stdout.write(JSON.stringify(summary, null, args.pretty ? 2 : 0));
    if (args.pretty) {
      process.stdout.write("\n");
    }
    return;
  }

  if (!args.target) {
    throw new Error("missing MCP target: pass --target or set DINGTALK_MCP_TARGET");
  }

  ensureMcporter();
  const schemaText = mcporterList(args.target);
  const missing = ensureRequiredTools(
    adapter,
    schemaText,
    args.createSheet,
    args.mode,
    args.copyTemplateStyle,
    args.styleTemplateSheet,
  );
  if (missing.length) {
    throw new Error(`configured tools are missing from MCP schema: ${missing.join(", ")}`);
  }

  const result = {
    ...summary,
    actions: [],
  };

  let sheetPrepared = false;
  if (args.createSheet) {
    const createPayload = renderArgs(adapter.tools.create_sheet.args, context);
    result.actions.push({
      tool: adapter.tools.create_sheet.name,
      args: createPayload,
      output: safeJson(mcporterCall(args.target, adapter.tools.create_sheet.name, createPayload)),
    });
    sheetPrepared = true;
  }

  ensureLiveIdColumn(args, adapter, schemaText, result);

  if (args.mode === "append-rows") {
    const appendPayload = renderArgs(adapter.tools.append_rows.args, context);
    const appendOutput = safeJson(mcporterCall(args.target, adapter.tools.append_rows.name, appendPayload));
    result.actions.push({
      tool: adapter.tools.append_rows.name,
      args: appendPayload,
      output: appendOutput,
    });
    if (appendOutput?.success) {
      const appendedRange = extractRowBoundsFromA1(appendOutput?.a1Notation);
      if (appendedRange) {
        mergeRanges =
          maybeConsolidateDateBlock(args, adapter, result, payload, appendedRange) ||
          buildMergeRanges(args, payload, values, appendedRange.startRow);
        result.merge_ranges = mergeRanges;
      }
    } else if (!sheetPrepared && isSheetNotFound(appendOutput)) {
      const createPayload = renderArgs(adapter.tools.create_sheet.args, context);
      const createOutput = safeJson(mcporterCall(args.target, adapter.tools.create_sheet.name, createPayload));
      result.actions.push({
        tool: adapter.tools.create_sheet.name,
        args: createPayload,
        output: createOutput,
      });
      sheetPrepared = true;

      const seededValues = [HEADER_ROW, ...buildValues(payload, false)];
      const seedArgs = {
        ...args,
        startRow: 1,
      };
      const seedContext = buildContext(seedArgs, seededValues);
      const updatePayload = renderArgs(adapter.tools.update_range.args, seedContext);
      const updateOutput = safeJson(mcporterCall(args.target, adapter.tools.update_range.name, updatePayload));
      result.actions.push({
        tool: adapter.tools.update_range.name,
        args: updatePayload,
        output: updateOutput,
      });
      applyTemplateStyle(args, adapter, schemaText, result);
      applyRepeatedDataRowStyle(args, adapter, schemaText, result, 2, payload.sheet_rows_sparse?.length || 0);
      unmergeRanges(
        args,
        adapter,
        schemaText,
        result,
        [
          ...buildTemplateDataMergeRanges(args, 2),
          ...buildRepeatedDataStyleMergeRanges(args, 2, payload.sheet_rows_sparse?.length || 0),
        ],
        "clear-template-data-merge",
      );
      mergeRanges = buildMergeRanges(
        {
          ...args,
          includeHeader: true,
          startRow: 1,
        },
        payload,
        seededValues,
        1,
      );
      result.merge_ranges = mergeRanges;
      unmergeRanges(args, adapter, schemaText, result, mergeRanges, "clear-template-merge-before-final-merge");
    }
  } else {
    const updatePayload = renderArgs(adapter.tools.update_range.args, context);
    result.actions.push({
      tool: adapter.tools.update_range.name,
      args: updatePayload,
      output: safeJson(mcporterCall(args.target, adapter.tools.update_range.name, updatePayload)),
    });
  }

  if (args.createSheet) {
    applyTemplateStyle(args, adapter, schemaText, result);
    const dataStartRow = args.includeHeader ? args.startRow + 1 : args.startRow;
    applyRepeatedDataRowStyle(args, adapter, schemaText, result, dataStartRow, payload.sheet_rows_sparse?.length || 0);
    unmergeRanges(
      args,
      adapter,
      schemaText,
      result,
      [
        ...buildTemplateDataMergeRanges(args, dataStartRow),
        ...buildRepeatedDataStyleMergeRanges(args, dataStartRow, payload.sheet_rows_sparse?.length || 0),
      ],
      "clear-template-data-merge",
    );
    unmergeRanges(args, adapter, schemaText, result, mergeRanges, "clear-template-merge-before-final-merge");
  }

  if (mergeRanges.length) {
    for (const mergeRange of mergeRanges) {
      const mergePayload = renderArgs(adapter.tools.merge_cells.args, {
        ...context,
        range_address: mergeRange,
      });
      result.actions.push({
        tool: adapter.tools.merge_cells.name,
        args: mergePayload,
        output: safeJson(mcporterCall(args.target, adapter.tools.merge_cells.name, mergePayload)),
      });
    }
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
