const fs = require("fs");
const path = require("path");

const DEFAULT_CONFIG_PATH = path.resolve(
  __dirname,
  "../../references/live-stream-api.local.json",
);

function loadConfig(configPath = DEFAULT_CONFIG_PATH, overrides = {}) {
  const resolved = process.env.LIVE_STREAM_API_CONFIG || configPath || DEFAULT_CONFIG_PATH;
  if (fs.existsSync(resolved)) {
    return normalizeConfig(JSON.parse(fs.readFileSync(resolved, "utf8")), overrides);
  }
  return normalizeConfig({
    baseUrl: process.env.LIVE_STREAM_BASE_URL || "https://lbk-mktadmin.codemao.cn",
    cookie: process.env.LIVE_STREAM_COOKIE || "",
    headers: {},
  }, overrides);
}

function normalizeConfig(raw, overrides = {}) {
  const baseUrl = (raw.baseUrl || "https://lbk-mktadmin.codemao.cn").replace(/\/$/, "");
  const cookie = overrides.cookie || process.env.LIVE_STREAM_COOKIE || raw.cookie || "";
  if (!cookie) {
    throw new Error(
      "missing live stream API cookie: pass --cookie, set LIVE_STREAM_COOKIE, or configure references/live-stream-api.local.json",
    );
  }
  return {
    baseUrl,
    cookie,
    headers: {
      accept: "application/json, text/plain, */*",
      "accept-language": "zh-CN,zh;q=0.9",
      origin: raw.origin || "https://lbk-operational.codemao.cn",
      referer: raw.referer || "https://lbk-operational.codemao.cn/",
      "user-agent":
        raw.userAgent ||
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      ...(raw.headers || {}),
      cookie,
    },
  };
}

async function fetchUserStatistics(liveStreamId, config = loadConfig()) {
  const id = String(liveStreamId).trim();
  if (!/^\d+$/.test(id)) {
    throw new Error(`invalid live stream id: ${liveStreamId}`);
  }

  const url = `${config.baseUrl}/live-stream/${id}/user-statistics`;
  const response = await fetch(url, {
    method: "GET",
    headers: config.headers,
  });

  const bodyText = await response.text();
  let body;
  try {
    body = JSON.parse(bodyText);
  } catch {
    throw new Error(`live stream API returned non-JSON (${response.status}): ${bodyText.slice(0, 200)}`);
  }

  if (!response.ok) {
    throw new Error(`live stream API HTTP ${response.status}: ${body.msg || bodyText.slice(0, 200)}`);
  }
  if (body.code !== 200 || body.success !== true) {
    throw new Error(`live stream API business error: ${body.msg || body.code}`);
  }

  const data = body.data || {};
  return {
    liveStreamId: id,
    onlineCount: data.onlineCount ?? 0,
    totalCount: data.totalCount ?? 0,
    reserveCount: data.reserveCount ?? 0,
    raw: body,
  };
}

module.exports = {
  DEFAULT_CONFIG_PATH,
  loadConfig,
  fetchUserStatistics,
};
