const fs = require("fs");
const path = require("path");
const cp = require("child_process");
const {
  DEFAULT_CONFIG_PATH,
  fetchUserStatistics,
  loadConfig,
} = require("./live_stream_api");
const {
  DEFAULT_LOGIN_URL,
  DEFAULT_PORT,
  DEFAULT_TIMEOUT_MS,
} = require("../login_live_stream_cookie");

const LOGIN_COOKIE = path.resolve(__dirname, "../login_live_stream_cookie.js");

function validateCookieShape(cookie) {
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

function readSavedCookie(configPath = DEFAULT_CONFIG_PATH) {
  if (!fs.existsSync(configPath)) {
    return "";
  }
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  return String(config.cookie || "").trim();
}

async function validateCookieByLive(cookie, configPath, liveId) {
  const config = loadConfig(configPath, { cookie });
  const stats = await fetchUserStatistics(liveId, config);
  return {
    live_id: String(liveId),
    totalCount: stats.totalCount,
    onlineCount: stats.onlineCount,
    reserveCount: stats.reserveCount,
  };
}

function runBrowserLoginCookie(args, validationLiveId) {
  const loginArgs = [
    LOGIN_COOKIE,
    "--config",
    args.config || DEFAULT_CONFIG_PATH,
    "--login-url",
    args.loginUrl || DEFAULT_LOGIN_URL,
    "--browser-port",
    String(args.loginPort || DEFAULT_PORT),
    "--login-timeout-ms",
    String(args.loginTimeoutMs || DEFAULT_TIMEOUT_MS),
  ];
  if (args.loginUserDataDir) {
    loginArgs.push("--browser-user-data-dir", args.loginUserDataDir);
  }
  if (args.chromePath) {
    loginArgs.push("--chrome-path", args.chromePath);
  }
  if (validationLiveId) {
    loginArgs.push("--validation-live-id", String(validationLiveId));
  }
  if (args.pretty) {
    loginArgs.push("--pretty");
  }
  return JSON.parse(cp.execFileSync(process.execPath, loginArgs, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
    env: process.env,
  }));
}

async function ensureValidLiveStreamCookie(args, validationLiveId) {
  const configPath = args.config || DEFAULT_CONFIG_PATH;
  let cookie = args.cookie || readSavedCookie(configPath);
  const source = args.cookie ? "argument" : cookie ? "config" : null;
  let validation = null;
  let validationError = null;

  if (cookie) {
    validateCookieShape(cookie);
  }

  if (cookie && validationLiveId) {
    try {
      validation = await validateCookieByLive(cookie, configPath, validationLiveId);
      return {
        cookie,
        source,
        refreshed: false,
        validation,
        login: null,
      };
    } catch (error) {
      validationError = error;
    }
  } else if (cookie) {
    return {
      cookie,
      source,
      refreshed: false,
      validation: {
        skipped: true,
        reason: "no validation live_id available",
      },
      login: null,
    };
  }

  if (args.autoLoginCookie === false || args.dryRun) {
    if (validationError) {
      throw new Error(`cookie validation failed: ${validationError.message}`);
    }
    throw new Error(
      "missing live stream API cookie: pass --cookie, configure references/live-stream-api.local.json, or enable browser login",
    );
  }

  const login = runBrowserLoginCookie({ ...args, config: configPath }, validationLiveId);
  cookie = readSavedCookie(configPath);
  if (!cookie) {
    throw new Error("browser login completed but no cookie was saved");
  }
  validateCookieShape(cookie);

  if (validationLiveId) {
    validation = await validateCookieByLive(cookie, configPath, validationLiveId);
  } else {
    validation = {
      skipped: true,
      reason: "no validation live_id available",
    };
  }

  return {
    cookie,
    source: "browser-login",
    refreshed: true,
    validation,
    login,
    previous_validation_error: validationError ? validationError.message : null,
  };
}

module.exports = {
  DEFAULT_CONFIG_PATH,
  DEFAULT_LOGIN_URL,
  DEFAULT_PORT,
  DEFAULT_TIMEOUT_MS,
  ensureValidLiveStreamCookie,
  readSavedCookie,
  validateCookieByLive,
  validateCookieShape,
};
