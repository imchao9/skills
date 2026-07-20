#!/usr/bin/env node

const crypto = require("crypto");
const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");
const cp = require("child_process");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");

const DEFAULT_CONFIG_PATH = path.resolve(
  __dirname,
  "../references/live-stream-api.local.json",
);
const EXAMPLE_CONFIG_PATH = path.resolve(
  __dirname,
  "../references/live-stream-api.local.example.json",
);
const DEFAULT_LOGIN_URL = "https://internal-account.codemao.cn/login";
const DEFAULT_PORT = 9222;
const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;
const CODEMAO_COOKIE_RE = /(^|\.)codemao\.cn$/i;
const USEFUL_COOKIE_NAMES = new Set([
  "internal_account_token",
  "admin-authorization",
  "dev_internal_account_token",
  "staging_internal_account_token",
  "test_internal_account_token",
  "staging-admin-authorization",
  "test-admin-authorization",
]);

function parseArgs(argv) {
  const args = {
    config: process.env.LIVE_STREAM_API_CONFIG || DEFAULT_CONFIG_PATH,
    loginUrl: process.env.LIVE_STREAM_LOGIN_URL || DEFAULT_LOGIN_URL,
    port: Number(process.env.LIVE_STREAM_LOGIN_DEBUG_PORT || DEFAULT_PORT),
    userDataDir:
      process.env.LIVE_STREAM_LOGIN_USER_DATA_DIR ||
      path.join(os.tmpdir(), "dingtalk-live-report-cookie-browser"),
    timeoutMs: Number(process.env.LIVE_STREAM_LOGIN_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
    validationLiveId: process.env.LIVE_STREAM_VALIDATION_LIVE_ID || null,
    chromePath: process.env.CHROME_PATH || null,
    chromeApp: process.env.CHROME_APP || "Google Chrome",
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--config":
        args.config = path.resolve(argv[++i]);
        break;
      case "--login-url":
        args.loginUrl = argv[++i];
        break;
      case "--port":
      case "--browser-port":
        args.port = Number(argv[++i]);
        break;
      case "--user-data-dir":
      case "--browser-user-data-dir":
        args.userDataDir = path.resolve(argv[++i]);
        break;
      case "--timeout-ms":
      case "--login-timeout-ms":
        args.timeoutMs = Number(argv[++i]);
        break;
      case "--validation-live-id":
        args.validationLiveId = argv[++i];
        break;
      case "--chrome-path":
        args.chromePath = argv[++i];
        break;
      case "--chrome-app":
        args.chromeApp = argv[++i];
        break;
      case "--pretty":
        args.pretty = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!Number.isFinite(args.port) || args.port <= 0) {
    throw new Error("invalid browser debug port");
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error("invalid login timeout");
  }
  return args;
}

function loadConfigForSaving(configPath) {
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

function saveCookie(configPath, cookie) {
  const config = loadConfigForSaving(configPath);
  config.cookie = cookie;
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

function launchBrowser(args) {
  fs.mkdirSync(args.userDataDir, { recursive: true });
  const chromeArgs = [
    `--remote-debugging-port=${args.port}`,
    `--user-data-dir=${args.userDataDir}`,
    "--no-first-run",
    "--no-default-browser-check",
    args.loginUrl,
  ];

  if (args.chromePath) {
    const child = cp.spawn(args.chromePath, chromeArgs, {
      detached: true,
      stdio: "ignore",
    });
    child.unref();
    return { process: child, closeWithCdp: true };
  }

  if (process.platform === "darwin") {
    const child = cp.spawn("open", ["-na", args.chromeApp, "--args", ...chromeArgs], {
      detached: true,
      stdio: "ignore",
    });
    child.unref();
    return { process: null, closeWithCdp: true };
  }

  const candidates = [
    process.env.GOOGLE_CHROME_BIN,
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      const child = cp.spawn(candidate, chromeArgs, {
        detached: true,
        stdio: "ignore",
      });
      child.unref();
      return { process: child, closeWithCdp: true };
    } catch {}
  }
  throw new Error("cannot launch Chrome/Chromium; pass --chrome-path");
}

async function connectBrowserCdp(port) {
  const version = await httpJson(`http://127.0.0.1:${port}/json/version`);
  if (!version.webSocketDebuggerUrl) {
    return null;
  }
  const browserCdp = new CdpWebSocket(version.webSocketDebuggerUrl);
  await browserCdp.connect();
  return browserCdp;
}

async function closeBrowser(cdp, launchedBrowser = null, port = null) {
  let closedByCdp = false;
  if (cdp) {
    try {
      await cdp.send("Browser.close");
      closedByCdp = true;
    } catch {}
  }

  if (!closedByCdp && port) {
    let browserCdp = null;
    try {
      browserCdp = await connectBrowserCdp(port);
      if (browserCdp) {
        await browserCdp.send("Browser.close");
        closedByCdp = true;
      }
    } catch {
    } finally {
      if (browserCdp) {
        browserCdp.close();
      }
    }
  }

  if (!closedByCdp && launchedBrowser?.process?.pid) {
    try {
      process.kill(-launchedBrowser.process.pid, "SIGTERM");
    } catch {
      try {
        launchedBrowser.process.kill("SIGTERM");
      } catch {}
    }
  }

  if (cdp) {
    cdp.close();
  }
}

async function httpJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForPageWebSocket(port, loginUrl, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let createdTarget = false;
  let lastError = null;

  while (Date.now() < deadline) {
    try {
      const pages = await httpJson(`http://127.0.0.1:${port}/json/list`);
      const page =
        pages.find((item) => item.type === "page" && item.url === loginUrl) ||
        pages.find((item) => item.type === "page" && !/^devtools:|^chrome:/i.test(item.url || "")) ||
        pages.find((item) => item.type === "page");
      if (page?.webSocketDebuggerUrl) {
        return page.webSocketDebuggerUrl;
      }

      if (!createdTarget) {
        createdTarget = true;
        try {
          await httpJson(
            `http://127.0.0.1:${port}/json/new?${encodeURIComponent(loginUrl)}`,
            { method: "PUT" },
          );
        } catch {
          await httpJson(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(loginUrl)}`);
        }
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(1000);
  }

  throw new Error(`timed out waiting for browser debug page: ${lastError?.message || "unknown"}`);
}

class CdpWebSocket {
  constructor(wsUrl) {
    const parsed = new URL(wsUrl);
    if (parsed.protocol !== "ws:") {
      throw new Error(`unsupported websocket protocol: ${parsed.protocol}`);
    }
    this.host = parsed.hostname;
    this.port = Number(parsed.port || 80);
    this.path = `${parsed.pathname}${parsed.search}`;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    const key = crypto.randomBytes(16).toString("base64");
    this.socket = net.createConnection({ host: this.host, port: this.port });
    this.socket.setNoDelay(true);

    await new Promise((resolve, reject) => {
      const onError = (error) => reject(error);
      this.socket.once("error", onError);
      this.socket.once("connect", () => {
        this.socket.write(
          [
            `GET ${this.path} HTTP/1.1`,
            `Host: ${this.host}:${this.port}`,
            "Upgrade: websocket",
            "Connection: Upgrade",
            `Sec-WebSocket-Key: ${key}`,
            "Sec-WebSocket-Version: 13",
            "\r\n",
          ].join("\r\n"),
        );
      });

      const chunks = [];
      const onData = (chunk) => {
        chunks.push(chunk);
        const raw = Buffer.concat(chunks);
        const headerEnd = raw.indexOf("\r\n\r\n");
        if (headerEnd < 0) {
          return;
        }
        this.socket.off("data", onData);
        this.socket.off("error", onError);
        const header = raw.slice(0, headerEnd).toString("utf8");
        if (!/^HTTP\/1\.1 101/i.test(header)) {
          reject(new Error(`websocket handshake failed: ${header.split("\r\n")[0]}`));
          return;
        }
        this.buffer = raw.slice(headerEnd + 4);
        this.socket.on("data", (data) => this.handleData(data));
        this.socket.on("error", (error) => this.rejectAll(error));
        this.socket.on("close", () => this.rejectAll(new Error("websocket closed")));
        this.handleFrames();
        resolve();
      };
      this.socket.on("data", onData);
    });
  }

  rejectAll(error) {
    for (const { reject } of this.pending.values()) {
      reject(error);
    }
    this.pending.clear();
  }

  handleData(data) {
    this.buffer = Buffer.concat([this.buffer, data]);
    this.handleFrames();
  }

  handleFrames() {
    while (this.buffer.length >= 2) {
      const first = this.buffer[0];
      const second = this.buffer[1];
      const opcode = first & 0x0f;
      let offset = 2;
      let length = second & 0x7f;

      if (length === 126) {
        if (this.buffer.length < offset + 2) return;
        length = this.buffer.readUInt16BE(offset);
        offset += 2;
      } else if (length === 127) {
        if (this.buffer.length < offset + 8) return;
        const high = this.buffer.readUInt32BE(offset);
        const low = this.buffer.readUInt32BE(offset + 4);
        length = high * 2 ** 32 + low;
        offset += 8;
      }

      const masked = Boolean(second & 0x80);
      let mask = null;
      if (masked) {
        if (this.buffer.length < offset + 4) return;
        mask = this.buffer.slice(offset, offset + 4);
        offset += 4;
      }
      if (this.buffer.length < offset + length) return;

      let payload = this.buffer.slice(offset, offset + length);
      this.buffer = this.buffer.slice(offset + length);

      if (masked) {
        payload = Buffer.from(payload.map((byte, index) => byte ^ mask[index % 4]));
      }

      if (opcode === 1) {
        this.handleMessage(payload.toString("utf8"));
      } else if (opcode === 8) {
        this.close();
      } else if (opcode === 9) {
        this.sendFrame(10, payload);
      }
    }
  }

  handleMessage(text) {
    let message;
    try {
      message = JSON.parse(text);
    } catch {
      return;
    }
    if (!message.id || !this.pending.has(message.id)) {
      return;
    }
    const { resolve, reject } = this.pending.get(message.id);
    this.pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message || JSON.stringify(message.error)));
    } else {
      resolve(message.result || {});
    }
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    this.sendFrame(1, Buffer.from(payload, "utf8"));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP command timed out: ${method}`));
        }
      }, 15000);
    });
  }

  sendFrame(opcode, payload) {
    const length = payload.length;
    let header;
    if (length < 126) {
      header = Buffer.alloc(2);
      header[1] = 0x80 | length;
    } else if (length < 65536) {
      header = Buffer.alloc(4);
      header[1] = 0x80 | 126;
      header.writeUInt16BE(length, 2);
    } else {
      header = Buffer.alloc(10);
      header[1] = 0x80 | 127;
      header.writeUInt32BE(0, 2);
      header.writeUInt32BE(length, 6);
    }
    header[0] = 0x80 | opcode;

    const mask = crypto.randomBytes(4);
    const maskedPayload = Buffer.from(payload);
    for (let i = 0; i < maskedPayload.length; i += 1) {
      maskedPayload[i] ^= mask[i % 4];
    }
    this.socket.write(Buffer.concat([header, mask, maskedPayload]));
  }

  close() {
    if (this.socket && !this.socket.destroyed) {
      this.socket.destroy();
    }
  }
}

function isCodemaoCookie(cookie) {
  return CODEMAO_COOKIE_RE.test(String(cookie.domain || "").replace(/^\./, ""));
}

function isUsefulCookie(cookie) {
  return USEFUL_COOKIE_NAMES.has(cookie.name) || /(^|-)authorization$/.test(cookie.name);
}

function buildCookieHeader(cookies) {
  const picked = new Map();
  for (const cookie of cookies) {
    if (!isCodemaoCookie(cookie)) {
      continue;
    }
    if (!cookie.name || cookie.value == null) {
      continue;
    }
    picked.set(cookie.name, `${cookie.name}=${cookie.value}`);
  }
  return [...picked.values()].join("; ");
}

function publicCookieNames(cookies) {
  return [...new Set(cookies.filter(isCodemaoCookie).map((cookie) => cookie.name))].sort();
}

async function readBrowserCookies(cdp) {
  try {
    await cdp.send("Network.enable");
  } catch {}
  try {
    const result = await cdp.send("Network.getAllCookies");
    return result.cookies || [];
  } catch {
    const result = await cdp.send("Storage.getCookies");
    return result.cookies || [];
  }
}

async function validateCookie(cookie, configPath, liveId) {
  const config = loadConfig(configPath, { cookie });
  const stats = await fetchUserStatistics(liveId, config);
  return {
    live_id: String(liveId),
    totalCount: stats.totalCount,
    onlineCount: stats.onlineCount,
    reserveCount: stats.reserveCount,
  };
}

async function waitForLoginCookie(args, cdp) {
  const deadline = Date.now() + args.timeoutMs;
  let lastValidationError = null;
  let lastCookieNames = [];

  while (Date.now() < deadline) {
    const cookies = await readBrowserCookies(cdp);
    lastCookieNames = publicCookieNames(cookies);
    const cookieHeader = buildCookieHeader(cookies);

    if (cookieHeader && args.validationLiveId) {
      try {
        const validation = await validateCookie(cookieHeader, args.config, args.validationLiveId);
        saveCookie(args.config, cookieHeader);
        return { cookieHeader, validation, cookieNames: lastCookieNames };
      } catch (error) {
        lastValidationError = error;
      }
    } else if (cookieHeader && cookies.some(isUsefulCookie)) {
      saveCookie(args.config, cookieHeader);
      return { cookieHeader, validation: null, cookieNames: lastCookieNames };
    }

    await sleep(2000);
  }

  const suffix = args.validationLiveId
    ? ` last validation error: ${lastValidationError?.message || "none"}`
    : ` seen cookies: ${lastCookieNames.join(", ") || "none"}`;
  throw new Error(`timed out waiting for valid login cookie.${suffix}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  process.stderr.write(
    `Opening ${args.loginUrl}. Please finish login in the browser window; cookie will be saved after validation.\n`,
  );
  const launchedBrowser = launchBrowser(args);
  let cdp = null;

  try {
    const wsUrl = await waitForPageWebSocket(args.port, args.loginUrl, Math.min(args.timeoutMs, 60000));
    cdp = new CdpWebSocket(wsUrl);
    await cdp.connect();
    const collected = await waitForLoginCookie(args, cdp);
    const payload = {
      ok: true,
      config: args.config,
      login_url: args.loginUrl,
      cookie_length: collected.cookieHeader.length,
      cookie_names: collected.cookieNames,
      validation: collected.validation,
      saved: true,
    };
    process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
  } finally {
    await closeBrowser(cdp, launchedBrowser, args.port);
  }
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  });
}

module.exports = {
  CdpWebSocket,
  DEFAULT_LOGIN_URL,
  DEFAULT_PORT,
  DEFAULT_TIMEOUT_MS,
  closeBrowser,
  connectBrowserCdp,
  launchBrowser,
  waitForPageWebSocket,
  sleep,
  readBrowserCookies,
  buildCookieHeader,
};
