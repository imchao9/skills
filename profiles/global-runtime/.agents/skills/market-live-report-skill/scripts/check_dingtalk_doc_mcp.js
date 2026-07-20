#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { ensureMcporter, mcporterList } = require("./lib/mcporter");

const DEFAULT_ADAPTER = path.resolve(__dirname, "../references/dingtalk-doc-adapter.example.json");

function parseArgs(argv) {
  const args = {
    adapter: DEFAULT_ADAPTER,
    target: process.env.DINGTALK_DOC_MCP_TARGET || "钉钉文档",
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--adapter") {
      args.adapter = argv[++i];
      continue;
    }
    if (token === "--target") {
      args.target = argv[++i];
      continue;
    }
    if (token === "--pretty") {
      args.pretty = true;
      continue;
    }
    throw new Error(`unexpected argument: ${token}`);
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const adapter = JSON.parse(fs.readFileSync(args.adapter, "utf8"));
  ensureMcporter();
  const schemaText = mcporterList(args.target);

  const requiredTools = Object.values(adapter.tools).map((entry) => entry.name);
  const present = [];
  const missing = [];

  for (const tool of requiredTools) {
    if (schemaText.includes(tool)) {
      present.push(tool);
    } else {
      missing.push(tool);
    }
  }

  const payload = {
    target: args.target,
    ok: missing.length === 0,
    present,
    missing,
    hint:
      missing.length > 0
        ? "可能配置了旧版文档 MCP。请从 https://mcp.dingtalk.com/#/detail?mcpId=9629 获取新版 URL。"
        : null,
  };

  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
  process.exit(payload.ok ? 0 : 1);
}

main();
