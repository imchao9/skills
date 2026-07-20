#!/usr/bin/env node

const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");

function parseArgs(argv) {
  const args = {
    liveId: null,
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
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const config = loadConfig(args.config, { cookie: args.cookie });
  const stats = await fetchUserStatistics(args.liveId, config);
  process.stdout.write(`${JSON.stringify(stats, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
