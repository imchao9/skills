#!/usr/bin/env node

const path = require("path");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const {
  defaultCacheDir,
  saveMilestoneSnapshot,
} = require("./lib/live_stats_cache");

function parseArgs(argv) {
  const args = {
    liveId: null,
    milestone: null,
    date: new Date().toISOString().slice(0, 10),
    cacheDir: defaultCacheDir(),
    pretty: false,
    config: null,
    cookie: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--live-id":
        args.liveId = argv[++i];
        break;
      case "--milestone":
        args.milestone = Number(argv[++i]);
        break;
      case "--date":
        args.date = argv[++i];
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

  if (!args.liveId) {
    throw new Error("pass --live-id <id>");
  }
  if (!Number.isFinite(args.milestone) || args.milestone <= 0) {
    throw new Error("pass --milestone <minutes>, e.g. 15");
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const config = loadConfig(args.config, { cookie: args.cookie });
  const stats = await fetchUserStatistics(args.liveId, config);
  const { cache, filePath } = saveMilestoneSnapshot(
    args.cacheDir,
    args.date,
    args.liveId,
    args.milestone,
    stats,
  );

  const payload = {
    date: args.date,
    liveId: String(args.liveId),
    milestone: args.milestone,
    stats,
    cacheFile: filePath,
    cache: cache.lives[String(args.liveId)],
  };

  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
