#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { parseText } = require("./parse_live_report");
const { fetchUserStatistics, loadConfig } = require("./lib/live_stream_api");
const {
  defaultCacheDir,
  saveMilestoneSnapshot,
  readCache,
} = require("./lib/live_stats_cache");
const {
  DEFAULT_CONFIG_PATH,
  DEFAULT_LOGIN_URL,
  DEFAULT_PORT,
  DEFAULT_TIMEOUT_MS,
  ensureValidLiveStreamCookie,
} = require("./lib/live_stream_cookie");

const DEFAULT_MILESTONES = [15, 20, 30];

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    year: new Date().getFullYear(),
    milestones: DEFAULT_MILESTONES,
    cacheDir: defaultCacheDir(),
    config: process.env.LIVE_STREAM_API_CONFIG || DEFAULT_CONFIG_PATH,
    dryRun: false,
    pretty: false,
    collectPast: false,
    pastGraceMinutes: 0,
    cookie: null,
    autoLoginCookie: true,
    loginUrl: process.env.LIVE_STREAM_LOGIN_URL || DEFAULT_LOGIN_URL,
    loginTimeoutMs: Number(process.env.LIVE_STREAM_LOGIN_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
    loginPort: Number(process.env.LIVE_STREAM_LOGIN_DEBUG_PORT || DEFAULT_PORT),
    loginUserDataDir: null,
    chromePath: process.env.CHROME_PATH || null,
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
      case "--milestones":
        args.milestones = parseMilestones(argv[++i]);
        break;
      case "--cache-dir":
        args.cacheDir = path.resolve(argv[++i]);
        break;
      case "--config":
        args.config = argv[++i];
        break;
      case "--cookie":
        args.cookie = argv[++i];
        break;
      case "--login-if-expired":
      case "--auto-login-cookie":
        args.autoLoginCookie = true;
        break;
      case "--no-login-if-expired":
      case "--no-auto-login-cookie":
        args.autoLoginCookie = false;
        break;
      case "--login-url":
        args.loginUrl = argv[++i];
        break;
      case "--login-timeout-ms":
        args.loginTimeoutMs = Number(argv[++i]);
        break;
      case "--browser-port":
      case "--login-port":
        args.loginPort = Number(argv[++i]);
        break;
      case "--browser-user-data-dir":
      case "--login-user-data-dir":
        args.loginUserDataDir = path.resolve(argv[++i]);
        break;
      case "--chrome-path":
        args.chromePath = argv[++i];
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--pretty":
        args.pretty = true;
        break;
      case "--collect-past":
        args.collectPast = true;
        break;
      case "--past-grace-minutes":
        args.pastGraceMinutes = Number(argv[++i]);
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw && !args.parsed) {
    throw new Error("pass --raw <file> or --parsed <file>");
  }
  if (!args.milestones.length) {
    throw new Error("pass at least one milestone");
  }
  return args;
}

function parseMilestones(value) {
  return String(value)
    .split(/[,\s，、]+/)
    .map((part) => Number(part.replace(/分钟/g, "")))
    .filter((minutes) => Number.isFinite(minutes) && minutes > 0);
}

function readParsed(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  return parseText(fs.readFileSync(args.raw, "utf8"), args.year);
}

function parseLocalDateTime(date, time) {
  const match = String(date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const timeMatch = String(time || "").match(/^(\d{1,2}):(\d{2})$/);
  if (!match || !timeMatch) {
    return null;
  }
  const [, year, month, day] = match;
  const [, hour, minute] = timeMatch;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0,
  );
}

function formatLocalDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join(" ");
}

function buildJobs(parsed, milestones, now = new Date()) {
  const jobs = [];
  for (const item of parsed.items || []) {
    const liveDate = item.live_date || parsed.meta?.date;
    const startAt = parseLocalDateTime(liveDate, item.time);
    if (!startAt) {
      throw new Error(`cannot parse start time for live_id=${item.live_id || ""}`);
    }

    for (const milestone of milestones) {
      const runAt = new Date(startAt.getTime() + milestone * 60 * 1000);
      jobs.push({
        date: liveDate,
        live_id: item.live_id,
        title: item.title,
        milestone,
        start_at: startAt.toISOString(),
        start_at_local: formatLocalDateTime(startAt),
        run_at: runAt.toISOString(),
        run_at_local: formatLocalDateTime(runAt),
        wait_ms: runAt.getTime() - now.getTime(),
      });
    }
  }
  return jobs.sort((left, right) => new Date(left.run_at) - new Date(right.run_at));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function collectJob(job, args, config) {
  const stats = await fetchUserStatistics(job.live_id, config);
  const { filePath } = saveMilestoneSnapshot(
    args.cacheDir,
    job.date,
    job.live_id,
    job.milestone,
    stats,
  );
  return {
    ...job,
    cache_file: filePath,
    stats,
    collected_at: new Date().toISOString(),
  };
}

async function runScheduler(args, parsed, cookieStatus = null) {
  const jobs = buildJobs(parsed, args.milestones);
  const results = [];

  for (const job of jobs) {
    const waitMs = new Date(job.run_at).getTime() - Date.now();
    const pastMs = Math.abs(Math.min(waitMs, 0));
    if (waitMs < 0 && !args.collectPast) {
      results.push({ ...job, status: "skipped-past" });
      continue;
    }
    if (
      waitMs < 0 &&
      args.pastGraceMinutes > 0 &&
      pastMs > args.pastGraceMinutes * 60 * 1000
    ) {
      results.push({ ...job, status: "skipped-past-grace" });
      continue;
    }

    if (waitMs > 0) {
      process.stderr.write(
        `waiting ${Math.ceil(waitMs / 1000)}s for live_id=${job.live_id} T+${job.milestone}\n`,
      );
      await sleep(waitMs);
    }

    try {
      const config = loadConfig(args.config, { cookie: args.cookie });
      const collected = await collectJob(job, args, config);
      results.push({ ...collected, status: "collected" });
      process.stderr.write(
        `collected live_id=${job.live_id} T+${job.milestone}: total=${collected.stats.totalCount}, online=${collected.stats.onlineCount}\n`,
      );
    } catch (error) {
      results.push({ ...job, status: "failed", error: error.message });
      process.stderr.write(`failed live_id=${job.live_id} T+${job.milestone}: ${error.message}\n`);
    }
  }

  const date = parsed.meta?.date || jobs[0]?.date;
  return {
    date,
    cookie: cookieStatus ? {
      source: cookieStatus.source,
      refreshed: cookieStatus.refreshed,
      validation: cookieStatus.validation,
      previous_validation_error: cookieStatus.previous_validation_error || null,
    } : null,
    cache_file: date ? path.join(args.cacheDir, `${date}.json`) : null,
    cache: date ? readCache(args.cacheDir, date) : null,
    results,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readParsed(args);
  if (parsed.errors?.length) {
    throw new Error(parsed.errors.join("; "));
  }

  const jobs = buildJobs(parsed, args.milestones);
  if (args.dryRun) {
    process.stdout.write(
      `${JSON.stringify(
        {
          now: new Date().toISOString(),
          cache_dir: args.cacheDir,
          jobs,
        },
        null,
        args.pretty ? 2 : 0,
      )}\n`,
    );
    return;
  }

  const cookieStatus = await ensureValidLiveStreamCookie(args, jobs[0]?.live_id || null);
  args.cookie = cookieStatus.cookie;
  const payload = await runScheduler(args, parsed, cookieStatus);
  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
