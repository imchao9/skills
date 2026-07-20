#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { parseText } = require("./parse_live_report");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const {
  defaultCacheDir,
  loadStatsMap,
  getMilestoneStats,
  readCache,
} = require("./lib/live_stats_cache");

const DEFAULT_MILESTONES = [15, 20, 30];
const DOCUMENT_FORMATS = new Set(["text", "markdown"]);

function parseArgs(argv) {
  const args = {
    parsed: null,
    raw: null,
    output: null,
    year: new Date().getFullYear(),
    pretty: false,
    milestones: [...DEFAULT_MILESTONES],
    statsCache: null,
    statsCacheDir: null,
    fetchMissing: false,
    includeResourceSection: false,
    config: null,
    cookie: null,
    format: "markdown",
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
      case "--output":
      case "-o":
        args.output = argv[++i];
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--milestones":
        args.milestones = argv[++i]
          .split(/[,\s，、]+/)
          .map((part) => Number(part.replace(/分钟/g, "")))
          .filter((value) => Number.isFinite(value) && value > 0);
        if (!args.milestones.length) {
          throw new Error("invalid --milestones value");
        }
        break;
      case "--stats-cache":
        args.statsCache = argv[++i];
        break;
      case "--stats-cache-dir":
        args.statsCacheDir = path.resolve(argv[++i]);
        break;
      case "--fetch-missing":
        args.fetchMissing = true;
        break;
      case "--include-resource-section":
        args.includeResourceSection = true;
        break;
      case "--config":
        args.config = argv[++i];
        break;
      case "--cookie":
        args.cookie = argv[++i];
        break;
      case "--format":
        args.format = normalizeDocumentFormat(argv[++i]);
        break;
      case "--markdown":
      case "--md":
        args.format = "markdown";
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.parsed && !args.raw) {
    throw new Error("pass --parsed <file> or --raw <file>");
  }
  if (!args.statsCacheDir) {
    args.statsCacheDir = defaultCacheDir();
  }
  return args;
}

function normalizeDocumentFormat(value) {
  const format = String(value || "").trim().toLowerCase();
  if (format === "md") {
    return "markdown";
  }
  if (!DOCUMENT_FORMATS.has(format)) {
    throw new Error("invalid --format, expected text or markdown");
  }
  return format;
}

function readPayload(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  const text = fs.readFileSync(args.raw, "utf8");
  return parseText(text, args.year);
}

function formatMetric(value) {
  if (value == null || value === "") {
    return "";
  }
  return String(value);
}

function dedupePreserveOrder(values) {
  const seen = new Set();
  const ordered = [];
  for (const value of values) {
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    ordered.push(value);
  }
  return ordered;
}

function buildDocumentTitle(date) {
  return `${date} 直播值班记录`;
}

function buildLiveSummaryLine(index, item) {
  const reserved =
    item.reserved != null ? item.reserved : item.reserve_from_api != null ? item.reserve_from_api : "";
  return `${index}. ${item.title}，预约人数：${formatMetric(reserved)}，覆盖：${formatMetric(item.coverage)}，预计：${formatMetric(item.estimated)}`;
}

function buildMilestoneLabel(minutes, index) {
  return index === 0 ? `${minutes}分钟 ` : `${minutes}分钟`;
}

function buildWatchAudienceLabel(itemIndex) {
  return itemIndex === 0 ? "观看人数" : "总观看人数";
}

function renderMilestoneBlock(minutes, milestoneIndex, stats) {
  const lines = [buildMilestoneLabel(minutes, milestoneIndex)];
  if (stats) {
    lines.push(`观看总人数：${formatMetric(stats.totalCount)}`);
    lines.push(`在线人数：${formatMetric(stats.onlineCount)}`);
  }
  return lines;
}

function escapeMarkdownTableCell(value) {
  return String(value ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\r?\n/g, "<br>");
}

function renderMarkdownStatsCell(stats) {
  if (!stats) {
    return "";
  }
  return [
    `实时观看：${formatMetric(stats.onlineCount)}`,
    `观看用户数：${formatMetric(stats.totalCount)}`,
    `预约直播：${formatMetric(stats.reserveCount)}`,
  ].join("<br>");
}

function loadStatsByLive(args = {}, parsed) {
  const warnings = [];
  if (args.statsCache) {
    const cache = JSON.parse(fs.readFileSync(args.statsCache, "utf8"));
    return { statsByLive: cache.lives || cache, warnings };
  }

  const date = parsed.meta?.date;
  if (!date) {
    warnings.push("missing meta.date; cannot load stats cache by date");
    return { statsByLive: {}, warnings };
  }

  const cacheDir = args.statsCacheDir || defaultCacheDir();
  return {
    statsByLive: loadStatsMap(cacheDir, date),
    warnings,
  };
}

async function resolveStatsForLive(args = {}, parsed, liveId, milestone, statsByLive, warnings) {
  const cached = getMilestoneStats({ lives: statsByLive }, liveId, milestone);
  if (cached) {
    return cached;
  }
  if (!args.fetchMissing) {
    warnings.push(`missing cached stats for live_id=${liveId} at ${milestone}min`);
    return null;
  }

  const config = loadConfig(args.config, { cookie: args.cookie });
  const stats = await fetchUserStatistics(liveId, config);
  warnings.push(
    `fetched live_id=${liveId} at ${milestone}min from API (real-time snapshot; collect at T+${milestone} for accuracy)`,
  );
  return {
    totalCount: stats.totalCount,
    onlineCount: stats.onlineCount,
    reserveCount: stats.reserveCount,
    fetchedAt: new Date().toISOString(),
  };
}

async function buildDutyDocumentText(parsed, options = {}) {
  if ((options.format || "text") === "markdown") {
    return buildDutyDocumentMarkdown(parsed, options);
  }

  const milestones = options.milestones || DEFAULT_MILESTONES;
  const items = parsed.items || [];
  const lines = [`${items.length}场直播`];
  const warnings = [...(options.warnings || [])];

  for (let itemIndex = 0; itemIndex < items.length; itemIndex += 1) {
    const item = items[itemIndex];
    lines.push(buildLiveSummaryLine(itemIndex + 1, item));
    lines.push("观看时长");
    lines.push(buildWatchAudienceLabel(itemIndex));

    for (let milestoneIndex = 0; milestoneIndex < milestones.length; milestoneIndex += 1) {
      const minutes = milestones[milestoneIndex];
      const stats = await resolveStatsForLive(
        options.args,
        parsed,
        item.live_id,
        minutes,
        options.statsByLive || {},
        warnings,
      );
      const block = renderMilestoneBlock(minutes, milestoneIndex, stats);
      lines.push(...block);
      if (milestoneIndex < milestones.length - 1) {
        lines.push("");
      }
    }

    lines.push("");
    lines.push("");
  }

  if (options.includeResourceSection) {
    milestones.forEach((minutes, index) => {
      lines.push(`${minutes}分钟资源整体使用情况`);
      lines.push("");
      lines.push("");
      lines.push("");
      if (index < milestones.length - 1) {
        lines.push("");
      }
    });
  }

  return { text: lines.join("\n"), warnings };
}

async function buildDutyDocumentMarkdown(parsed, options = {}) {
  const milestones = options.milestones || DEFAULT_MILESTONES;
  const items = parsed.items || [];
  const lines = [`${items.length}场直播`, ""];
  const warnings = [...(options.warnings || [])];

  for (let itemIndex = 0; itemIndex < items.length; itemIndex += 1) {
    const item = items[itemIndex];
    const summary = buildLiveSummaryLine(itemIndex + 1, item).replace(
      item.title,
      `**${item.title}**`,
    );
    lines.push(summary);
    lines.push("");
    lines.push("| 观看时长 | 总观看人数 |");
    lines.push("| --- | --- |");

    for (const minutes of milestones) {
      const stats = await resolveStatsForLive(
        options.args,
        parsed,
        item.live_id,
        minutes,
        options.statsByLive || {},
        warnings,
      );
      lines.push(
        `| ${escapeMarkdownTableCell(`${minutes}分钟`)} | ${escapeMarkdownTableCell(
          renderMarkdownStatsCell(stats),
        )} |`,
      );
    }

    lines.push("");
  }

  if (options.includeResourceSection) {
    milestones.forEach((minutes) => {
      lines.push(`### ${minutes}分钟资源整体使用情况`);
      lines.push("");
    });
  }

  return { text: lines.join("\n").trimEnd(), warnings };
}

async function buildDutyDocumentPayload(parsed, options = {}) {
  const milestones = options.milestones || DEFAULT_MILESTONES;
  const warnings = [...(parsed.warnings || []), ...(options.warnings || [])];
  const { statsByLive, warnings: cacheWarnings } = loadStatsByLive(options.args, parsed);
  warnings.push(...cacheWarnings);

  (parsed.items || []).forEach((item, index) => {
    if (item.reserved == null) {
      const firstStats = milestonesFirstReserve(statsByLive, item.live_id, milestones);
      if (firstStats?.reserveCount != null) {
        item.reserve_from_api = firstStats.reserveCount;
      } else {
        warnings.push(`item ${index + 1} missing reserved (预约人数)`);
      }
    }
  });

  const built = await buildDutyDocumentText(parsed, {
    milestones,
    statsByLive,
    warnings: [],
    args: options.args,
    includeResourceSection: options.includeResourceSection,
    format: options.format,
  });

  const date = parsed.meta?.date;
  return {
    title: date ? buildDocumentTitle(date) : null,
    meta: parsed.meta,
    live_count: (parsed.items || []).length,
    milestones,
    format: options.format || "text",
    text: built.text,
    warnings: dedupePreserveOrder([...warnings, ...built.warnings]),
    errors: parsed.errors || [],
    stats_cache: date
      ? readCache(options.args?.statsCacheDir || defaultCacheDir(), date)
      : null,
  };
}

function milestonesFirstReserve(statsByLive, liveId, milestones) {
  const liveStats = statsByLive?.[String(liveId)] || {};
  for (const milestone of milestones || DEFAULT_MILESTONES) {
    const stats = liveStats[String(milestone)];
    if (stats?.reserveCount != null) {
      return stats;
    }
  }
  return null;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readPayload(args);
  if (parsed.errors && parsed.errors.length) {
    process.stderr.write(`${parsed.errors.join("; ")}\n`);
    process.exit(1);
  }

  const payload = await buildDutyDocumentPayload(parsed, {
    milestones: args.milestones,
    includeResourceSection: args.includeResourceSection,
    format: args.format,
    args,
  });

  if (args.output) {
    fs.writeFileSync(args.output, `${payload.text}\n`, "utf8");
  } else if (!args.pretty) {
    process.stdout.write(payload.text);
    if (!payload.text.endsWith("\n")) {
      process.stdout.write("\n");
    }
  } else {
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  }

  process.exit(0);
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  });
}

module.exports = {
  buildDocumentTitle,
  buildDutyDocumentText,
  buildDutyDocumentPayload,
  DEFAULT_MILESTONES,
  normalizeDocumentFormat,
  buildLiveSummaryLine,
  buildWatchAudienceLabel,
  renderMilestoneBlock,
  renderMarkdownStatsCell,
};
