const fs = require("fs");
const path = require("path");

function defaultCacheDir() {
  return path.resolve(__dirname, "../../references/live-stats-cache");
}

function cachePathForDate(cacheDir, date) {
  return path.join(cacheDir, `${date}.json`);
}

function emptyCache(date) {
  return {
    date,
    lives: {},
    updatedAt: null,
  };
}

function readCache(cacheDir, date) {
  const filePath = cachePathForDate(cacheDir, date);
  if (!fs.existsSync(filePath)) {
    return emptyCache(date);
  }
  const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return {
    date: parsed.date || date,
    lives: parsed.lives || {},
    updatedAt: parsed.updatedAt || null,
  };
}

function writeCache(cacheDir, cache) {
  fs.mkdirSync(cacheDir, { recursive: true });
  const payload = {
    ...cache,
    updatedAt: new Date().toISOString(),
  };
  const filePath = cachePathForDate(cacheDir, cache.date);
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return filePath;
}

function saveMilestoneSnapshot(cacheDir, date, liveStreamId, milestone, stats) {
  const cache = readCache(cacheDir, date);
  const liveId = String(liveStreamId);
  if (!cache.lives[liveId]) {
    cache.lives[liveId] = {};
  }
  cache.lives[liveId][String(milestone)] = {
    totalCount: stats.totalCount,
    onlineCount: stats.onlineCount,
    reserveCount: stats.reserveCount,
    fetchedAt: new Date().toISOString(),
  };
  const filePath = writeCache(cacheDir, cache);
  return { cache, filePath };
}

function getMilestoneStats(cache, liveStreamId, milestone) {
  return cache?.lives?.[String(liveStreamId)]?.[String(milestone)] || null;
}

function loadStatsMap(cacheDir, date) {
  return readCache(cacheDir, date).lives;
}

module.exports = {
  defaultCacheDir,
  cachePathForDate,
  readCache,
  writeCache,
  saveMilestoneSnapshot,
  getMilestoneStats,
  loadStatsMap,
};
