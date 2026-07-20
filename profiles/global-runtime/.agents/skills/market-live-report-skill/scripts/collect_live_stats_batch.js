#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { parseText } = require("./parse_live_report");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const {
  defaultCacheDir,
  saveMilestoneSnapshot,
  readCache,
} = require("./lib/live_stats_cache");

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    milestone: null,
    date: null,
    year: new Date().getFullYear(),
    cacheDir: defaultCacheDir(),
    pretty: false,
    config: null,
    cookie: null,
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
      case "--milestone":
        args.milestone = Number(argv[++i]);
        break;
      case "--date":
        args.date = argv[++i];
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--cache-dir":
        args.cacheDir = path.resolve(argv[++i]);
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--config":
        args.config = argv[++i];
        break;
      case "--cookie":
        args.cookie = argv[++i];
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw && !args.parsed) {
    throw new Error("pass --raw <file> or --parsed <file>");
  }
  if (!Number.isFinite(args.milestone) || args.milestone <= 0) {
    throw new Error("pass --milestone <minutes>, e.g. 15");
  }
  return args;
}

function readParsed(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  return parseText(fs.readFileSync(args.raw, "utf8"), args.year);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readParsed(args);
  if (parsed.errors?.length) {
    throw new Error(parsed.errors.join("; "));
  }

  const date = args.date || parsed.meta?.date;
  if (!date) {
    throw new Error("missing date: pass --date or include 日期 in report");
  }

  const config = loadConfig(args.config, { cookie: args.cookie });
  const results = [];

  for (const item of parsed.items || []) {
    const stats = await fetchUserStatistics(item.live_id, config);
    saveMilestoneSnapshot(args.cacheDir, date, item.live_id, args.milestone, stats);
    results.push({
      live_id: item.live_id,
      title: item.title,
      milestone: args.milestone,
      stats,
    });
  }

  const payload = {
    date,
    milestone: args.milestone,
    cache_file: path.join(args.cacheDir, `${date}.json`),
    cache: readCache(args.cacheDir, date),
    results,
  };

  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
