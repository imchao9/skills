#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { parseText } = require("./parse_live_report");
const {
  buildDutyDocumentPayload,
  buildDocumentTitle,
  normalizeDocumentFormat,
} = require("./build_duty_document");
const { defaultCacheDir } = require("./lib/live_stats_cache");
const cp = require("child_process");

const CREATE_DINGTALK_DOC = path.resolve(__dirname, "./create_dingtalk_duty_document.js");

const DEFAULT_FOLDER_CONFIG = path.resolve(
  __dirname,
  "../references/duty-docs-folder.local.json",
);
const DEFAULT_OUTPUT_DIR = path.resolve(__dirname, "../output/duty-docs");
const DEFAULT_MONITOR_ASSETS_DIR = path.resolve(DEFAULT_OUTPUT_DIR, "assets");

function loadFolderConfig(configPath = DEFAULT_FOLDER_CONFIG) {
  const resolved = process.env.DUTY_DOCS_FOLDER_CONFIG || configPath;
  if (!fs.existsSync(resolved)) {
    return {
      folder_node_id:
        process.env.DUTY_DOCS_FOLDER_NODE_ID ||
        "https://alidocs.dingtalk.com/i/nodes/a9E05BDRVQ6AaedDFp9D6klbJ63zgkYA",
      title_template: "{date} 直播值班记录",
    };
  }
  return JSON.parse(fs.readFileSync(resolved, "utf8"));
}

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    year: new Date().getFullYear(),
    pretty: false,
    outputDir: DEFAULT_OUTPUT_DIR,
    statsCacheDir: defaultCacheDir(),
    fetchMissing: false,
    includeResourceSection: false,
    folderConfig: DEFAULT_FOLDER_CONFIG,
    dryRun: false,
    dingtalkDoc: false,
    docTarget: process.env.DINGTALK_DOC_MCP_TARGET || "钉钉文档",
    config: null,
    cookie: null,
    format: "markdown",
    includeMonitorScreenshots: false,
    monitorScreenshotDir: DEFAULT_MONITOR_ASSETS_DIR,
    embedLocalMonitorScreenshots: false,
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
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--output-dir":
        args.outputDir = path.resolve(argv[++i]);
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
      case "--folder-config":
        args.folderConfig = argv[++i];
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--dingtalk-doc":
        args.dingtalkDoc = true;
        break;
      case "--doc-target":
        args.docTarget = argv[++i];
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
      case "--include-monitor-screenshots":
        args.includeMonitorScreenshots = true;
        break;
      case "--embed-local-monitor-screenshots":
        args.embedLocalMonitorScreenshots = true;
        break;
      case "--monitor-screenshot-dir":
        args.monitorScreenshotDir = path.resolve(argv[++i]);
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw && !args.parsed) {
    throw new Error("pass --raw <file> or --parsed <file>");
  }
  return args;
}

function readParsed(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  return parseText(fs.readFileSync(args.raw, "utf8"), args.year);
}

function sanitizeFileName(title) {
  return title.replace(/[\\/:*?"<>|]/g, "_");
}

function listMonitorScreenshots(args, date) {
  const dateDir = path.join(args.monitorScreenshotDir, date);
  if (!fs.existsSync(dateDir)) {
    return [];
  }
  const files = fs
    .readdirSync(dateDir)
    .filter((fileName) => /\.(png|jpe?g|webp)$/i.test(fileName))
    .sort();
  const latestBySlot = new Map();
  const unmatched = [];
  for (const fileName of files) {
    const match = fileName.match(
      /^monitor-(.+)-T(\d+)-\d{8}-\d{6}-captured-(\d{8}-\d{6})\.(png|jpe?g|webp)$/i,
    );
    if (!match) {
      unmatched.push(fileName);
      continue;
    }
    const [, section, milestone, capturedAt] = match;
    const key = `${milestone}:${section}`;
    const previous = latestBySlot.get(key);
    if (!previous || capturedAt > previous.capturedAt) {
      latestBySlot.set(key, { fileName, section, milestone: Number(milestone), capturedAt });
    }
  }
  const sectionOrder = new Map([
    ["overview", 1],
    ["microservice-pod-curves", 2],
    ["database-overviews", 3],
  ]);
  const matched = [...latestBySlot.values()].sort(
    (left, right) =>
      left.milestone - right.milestone ||
      (sectionOrder.get(left.section) || 99) - (sectionOrder.get(right.section) || 99) ||
      left.fileName.localeCompare(right.fileName),
  );
  return [...matched.map((entry) => entry.fileName), ...unmatched].map((fileName) =>
    path.join(dateDir, fileName),
  );
}

function parseMonitorScreenshot(filePath) {
  const fileName = path.basename(filePath);
  const match = fileName.match(/^monitor-(.+)-T(\d+)-/i);
  const sectionLabels = new Map([
    ["overview", "顶部概览"],
    ["microservice-pod-curves", "微服务与Pod资源曲线图"],
    ["database-overviews", "数据库Overviews"],
  ]);
  if (!match) {
    return {
      filePath,
      milestone: Number.POSITIVE_INFINITY,
      section: "unknown",
      label: path.basename(filePath, path.extname(filePath)),
    };
  }
  const [, section, milestone] = match;
  return {
    filePath,
    milestone: Number(milestone),
    section,
    label: sectionLabels.get(section) || section,
  };
}

function groupMonitorScreenshots(files) {
  const sectionOrder = new Map([
    ["overview", 1],
    ["microservice-pod-curves", 2],
    ["database-overviews", 3],
  ]);
  const groups = new Map();
  for (const filePath of files) {
    const entry = parseMonitorScreenshot(filePath);
    const key = Number.isFinite(entry.milestone) ? entry.milestone : "其他";
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(entry);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => Number(left) - Number(right))
    .map(([milestone, entries]) => ({
      milestone,
      entries: entries.sort(
        (left, right) =>
          (sectionOrder.get(left.section) || 99) -
            (sectionOrder.get(right.section) || 99) ||
          left.filePath.localeCompare(right.filePath),
      ),
    }));
}

function renderMonitorScreenshotsSection(files, format, options = {}) {
  if (!files.length) {
    return "";
  }
  const groups = groupMonitorScreenshots(files);
  if (format === "markdown") {
    const lines = [""];
    groups.forEach((group) => {
      const title =
        group.milestone === "其他" ? "其他资源整体使用情况" : `${group.milestone}分钟资源整体使用情况`;
      lines.push(`## ${title}`);
      lines.push("");
      group.entries.forEach((entry) => {
        lines.push(`![${entry.label}](${entry.filePath})`);
        lines.push("");
      });
      lines.push("");
    });
    return lines.join("\n").trimEnd();
  }

  const lines = [""];
  groups.forEach((group) => {
    const title =
      group.milestone === "其他" ? "其他资源整体使用情况" : `${group.milestone}分钟资源整体使用情况`;
    lines.push(title);
    lines.push("");
    group.entries.forEach((entry) => {
      lines.push(`${entry.label}：${entry.filePath}`);
      lines.push("");
    });
    lines.push("");
  });
  return lines.join("\n").trimEnd();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readParsed(args);
  if (parsed.errors?.length) {
    throw new Error(parsed.errors.join("; "));
  }

  const folderConfig = loadFolderConfig(args.folderConfig);
  const date = parsed.meta?.date;
  if (!date) {
    throw new Error("parsed payload missing meta.date");
  }

  const title =
    (folderConfig.title_template || "{date} 直播值班记录").replace("{date}", date) ||
    buildDocumentTitle(date);

  const builderArgs = {
    milestones: [15, 20, 30],
    includeResourceSection: args.includeResourceSection,
    format: args.format,
    args: {
      statsCacheDir: args.statsCacheDir,
      fetchMissing: args.fetchMissing,
      config: args.config,
      cookie: args.cookie,
    },
  };

  const payload = await buildDutyDocumentPayload(parsed, builderArgs);
  if (args.includeMonitorScreenshots) {
    const screenshots = listMonitorScreenshots(args, date);
    const section = renderMonitorScreenshotsSection(screenshots, args.format, {
      embedLocalImages: args.embedLocalMonitorScreenshots,
    });
    if (section) {
      payload.text = `${payload.text.trimEnd()}\n\n${section}`;
    }
    payload.monitor_screenshots = screenshots;
  }
  const bodyExtension = args.format === "markdown" ? "md" : "txt";
  const bodyFileName = `${sanitizeFileName(title)}.${bodyExtension}`;
  const metaFileName = `${sanitizeFileName(title)}.meta.json`;

  const result = {
    title,
    date,
    folder_node_id: folderConfig.folder_node_id,
    body_file: null,
    meta_file: null,
    dingtalk_doc: null,
    document: payload,
  };

  if (!args.dryRun) {
    fs.mkdirSync(args.outputDir, { recursive: true });
    const bodyPath = path.join(args.outputDir, bodyFileName);
    const metaPath = path.join(args.outputDir, metaFileName);
    fs.writeFileSync(bodyPath, `${payload.text}\n`, "utf8");
    fs.writeFileSync(
      metaPath,
      `${JSON.stringify(
        {
          title,
          date,
          folder_node_id: folderConfig.folder_node_id,
          body_format: args.format,
          monitor_screenshots: payload.monitor_screenshots || [],
          embed_local_monitor_screenshots: args.embedLocalMonitorScreenshots,
          warnings: payload.warnings,
          stats_cache_file: path.join(args.statsCacheDir, `${date}.json`),
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
    result.body_file = bodyPath;
    result.meta_file = metaPath;
  }

  if (args.dingtalkDoc) {
    const createArgs = [CREATE_DINGTALK_DOC];
    if (args.raw) {
      createArgs.push("--raw", args.raw);
    } else {
      createArgs.push("--parsed", args.parsed);
    }
    createArgs.push("--stats-cache-dir", args.statsCacheDir, "--target", args.docTarget);
    if (args.config) {
      createArgs.push("--config", args.config);
    }
    if (args.cookie) {
      createArgs.push("--cookie", args.cookie);
    }
    if (args.fetchMissing) {
      createArgs.push("--fetch-missing");
    }
    if (args.includeResourceSection) {
      createArgs.push("--include-resource-section");
    }
    if (args.format !== "text") {
      createArgs.push("--format", args.format);
    }
    if (args.includeMonitorScreenshots) {
      createArgs.push(
        "--include-monitor-screenshots",
        "--monitor-screenshot-dir",
        args.monitorScreenshotDir,
      );
    }
    if (args.embedLocalMonitorScreenshots) {
      createArgs.push("--embed-local-monitor-screenshots");
    }
    if (args.dryRun) {
      createArgs.push("--dry-run");
    }
    if (args.pretty) {
      createArgs.push("--pretty");
    }
    try {
      const raw = cp.execFileSync(process.execPath, createArgs, {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
      });
      result.dingtalk_doc = JSON.parse(raw);
    } catch (error) {
      const stderr = error.stderr ? String(error.stderr) : "";
      throw new Error(`dingtalk doc MCP failed: ${stderr || error.message}`);
    }
  } else {
    result.dingtalk_create_hint =
      "未启用 --dingtalk-doc。配置 mcpId=9629 文档 MCP 后使用，见 references/dingtalk-doc-mcp.md";
  }

  process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
