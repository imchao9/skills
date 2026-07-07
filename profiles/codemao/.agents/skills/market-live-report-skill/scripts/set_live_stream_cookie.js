#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const DEFAULT_CONFIG_PATH = path.resolve(
  __dirname,
  "../references/live-stream-api.local.json",
);
const EXAMPLE_CONFIG_PATH = path.resolve(
  __dirname,
  "../references/live-stream-api.local.example.json",
);

function parseArgs(argv) {
  const args = {
    config: process.env.LIVE_STREAM_API_CONFIG || DEFAULT_CONFIG_PATH,
    cookie: null,
    stdin: false,
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--config":
        args.config = path.resolve(argv[++i]);
        break;
      case "--cookie":
        args.cookie = argv[++i];
        break;
      case "--stdin":
        args.stdin = true;
        break;
      case "--pretty":
        args.pretty = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.cookie && !args.stdin) {
    args.stdin = true;
  }
  return args;
}

function readStdin() {
  return fs.readFileSync(0, "utf8").trim();
}

function loadConfig(configPath) {
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

function validateCookie(cookie) {
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

function main() {
  const args = parseArgs(process.argv.slice(2));
  const cookie = args.cookie || readStdin();
  validateCookie(cookie);

  const config = loadConfig(args.config);
  config.cookie = cookie;

  fs.mkdirSync(path.dirname(args.config), { recursive: true });
  fs.writeFileSync(args.config, `${JSON.stringify(config, null, 2)}\n`, "utf8");

  const payload = {
    ok: true,
    config: args.config,
    cookie_length: cookie.length,
    hint: "Cookie saved locally. Do not commit references/*.local.json.",
  };
  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
}
