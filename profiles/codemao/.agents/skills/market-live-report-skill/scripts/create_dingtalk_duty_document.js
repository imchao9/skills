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
const {
  ensureMcporter,
  mcporterList,
  mcporterCall,
  safeJson,
  renderArgs,
  findNodeIdDeep,
} = require("./lib/mcporter");
const {
  listMonitorScreenshots,
  renderMonitorScreenshotsSection,
} = require("./lib/monitor_screenshots");
const { uploadFilesToDingtalk } = require("./lib/dingtalk_file_upload");

const DEFAULT_ADAPTER = path.resolve(__dirname, "../references/dingtalk-doc-adapter.example.json");
const DEFAULT_FOLDER_CONFIG = path.resolve(__dirname, "../references/duty-docs-folder.local.json");

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

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
  return loadJson(resolved);
}

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    year: new Date().getFullYear(),
    pretty: false,
    dryRun: false,
    target: process.env.DINGTALK_DOC_MCP_TARGET || "钉钉文档",
    adapter: DEFAULT_ADAPTER,
    folderConfig: DEFAULT_FOLDER_CONFIG,
    statsCacheDir: defaultCacheDir(),
    fetchMissing: false,
    includeResourceSection: false,
    updateIfExists: true,
    config: null,
    cookie: null,
    format: "markdown",
    includeMonitorScreenshots: false,
    monitorScreenshotDir: path.resolve(__dirname, "../output/duty-docs/assets"),
    uploadMonitorScreenshots: true,
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
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--target":
        args.target = argv[++i];
        break;
      case "--adapter":
        args.adapter = argv[++i];
        break;
      case "--folder-config":
        args.folderConfig = argv[++i];
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
      case "--include-monitor-screenshots":
        args.includeMonitorScreenshots = true;
        break;
      case "--no-upload-monitor-screenshots":
        args.uploadMonitorScreenshots = false;
        break;
      case "--monitor-screenshot-dir":
        args.monitorScreenshotDir = path.resolve(argv[++i]);
        break;
      case "--no-update-if-exists":
        args.updateIfExists = false;
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

function plainTextToMarkdown(title, body) {
  const markdownBody = body
    .split("\n")
    .map((line) => (line ? `${line}  ` : ""))
    .join("\n");
  return `# ${title}\n\n${markdownBody}\n`;
}

function callAdapterTool(adapter, target, toolKey, context) {
  const entry = adapter.tools[toolKey];
  if (!entry) {
    throw new Error(`adapter missing tool: ${toolKey}`);
  }
  const payload = renderArgs(entry.args, context);
  const raw = mcporterCall(target, entry.name, payload);
  return safeJson(raw);
}

function findExistingDocument(searchOutput, title) {
  const candidates = [];
  const walk = (node) => {
    if (!node || typeof node !== "object") {
      return;
    }
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    const name = node.name || node.title || node.docName;
    if (name && String(name).trim() === title) {
      candidates.push(node);
    }
    Object.values(node).forEach(walk);
  };
  walk(searchOutput);
  return candidates[0] || null;
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

  const documentPayload = await buildDutyDocumentPayload(parsed, {
    milestones: [15, 20, 30],
    includeResourceSection: args.includeResourceSection,
    format: args.format,
    args: {
      statsCacheDir: args.statsCacheDir,
      fetchMissing: args.fetchMissing,
      config: args.config,
      cookie: args.cookie,
    },
  });

  const adapter = loadJson(args.adapter);
  let schemaText = "";
  if (!args.dryRun) {
    ensureMcporter();
    schemaText = mcporterList(args.target);
    if (!schemaText.includes(adapter.tools.create_document.name)) {
      throw new Error(
        `target "${args.target}" does not expose create_document. Configure 钉钉文档 MCP (mcpId=9629). See references/dingtalk-doc-mcp.md`,
      );
    }
    if (
      args.includeMonitorScreenshots &&
      args.uploadMonitorScreenshots &&
      !schemaText.includes(adapter.tools.get_file_upload_info.name)
    ) {
      throw new Error(
        `target "${args.target}" does not expose get_file_upload_info. Configure a DingTalk doc MCP version with file upload support.`,
      );
    }
  }

  let uploadedMonitorScreenshots = [];
  if (args.includeMonitorScreenshots) {
    const screenshots = listMonitorScreenshots(args.monitorScreenshotDir, date);
    if (!args.dryRun && args.uploadMonitorScreenshots && screenshots.length) {
      uploadedMonitorScreenshots = await uploadFilesToDingtalk(adapter, args.target, screenshots, {
        folderId: folderConfig.folder_node_id,
      });
    }
    const section = renderMonitorScreenshotsSection(screenshots, args.format, {
      uploaded: uploadedMonitorScreenshots,
    });
    if (section) {
      documentPayload.text = `${documentPayload.text.trimEnd()}\n\n${section}`;
    }
    documentPayload.monitor_screenshots = screenshots;
    documentPayload.uploaded_monitor_screenshots = uploadedMonitorScreenshots;
  }

  const markdown =
    args.format === "markdown"
      ? `# ${title}\n\n${documentPayload.text}\n`
      : plainTextToMarkdown(title, documentPayload.text);
  const context = {
    name: title,
    markdown,
    folder_id: folderConfig.folder_node_id,
    keyword: title,
    mode: "overwrite",
  };

  const result = {
    title,
    date,
    folder_node_id: folderConfig.folder_node_id,
    dry_run: args.dryRun,
    action: null,
    node_id: null,
    mcp_response: null,
    monitor_screenshots: documentPayload.monitor_screenshots || [],
    uploaded_monitor_screenshots: uploadedMonitorScreenshots.map((entry) => ({
      file_path: entry.file_path,
      name: entry.name,
      node_id: entry.node_id,
      url: entry.url,
    })),
    warnings: documentPayload.warnings,
  };

  if (args.dryRun) {
    result.action = "dry-run";
    result.markdown_preview = markdown.slice(0, 500);
    process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
    return;
  }

  let nodeId = null;
  let action = "create";

  if (args.updateIfExists && adapter.tools.search_documents && schemaText.includes(adapter.tools.search_documents.name)) {
    const searchOutput = callAdapterTool(adapter, args.target, "search_documents", context);
    const existing = findExistingDocument(searchOutput, title);
    nodeId = findNodeIdDeep(existing);
    if (nodeId) {
      action = "update";
      context.node_id = nodeId;
      result.mcp_response = callAdapterTool(adapter, args.target, "update_document", context);
    }
  }

  if (!nodeId) {
    action = "create";
    result.mcp_response = callAdapterTool(adapter, args.target, "create_document", context);
    nodeId = findNodeIdDeep(result.mcp_response);
  }

  result.action = action;
  result.node_id = nodeId;
  result.document_url = nodeId
    ? `https://alidocs.dingtalk.com/i/nodes/${nodeId}`
    : null;

  process.stdout.write(`${JSON.stringify(result, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
