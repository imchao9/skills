#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const cp = require("child_process");

const DEFAULT_ADAPTER = path.resolve(
  __dirname,
  "../references/dingtalk-spreadsheet-adapter.example.json",
);

function parseArgs(argv) {
  const args = {
    adapter: DEFAULT_ADAPTER,
    target: process.env.DINGTALK_MCP_TARGET || null,
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

  if (!args.target) {
    throw new Error("missing MCP target: pass --target or set DINGTALK_MCP_TARGET");
  }

  return args;
}

function loadAdapter(adapterPath) {
  return JSON.parse(fs.readFileSync(adapterPath, "utf8"));
}

function runMcporter(target) {
  try {
    return cp.execFileSync("mcporter", ["list", target, "--schema"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const stderr = error.stderr ? String(error.stderr) : "";
    if (error.code === "ENOENT") {
      throw new Error("mcporter not found in PATH");
    }
    throw new Error(`failed to inspect MCP schema: ${stderr || error.message}`);
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const adapter = loadAdapter(args.adapter);
  const schemaText = runMcporter(args.target);

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
    adapter: path.resolve(args.adapter),
    present_tools: present,
    missing_tools: missing,
    ok: missing.length === 0,
  };

  process.stdout.write(JSON.stringify(payload, null, args.pretty ? 2 : 0));
  if (args.pretty) {
    process.stdout.write("\n");
  }
  process.exit(payload.ok ? 0 : 1);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
}
