const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const offlineDataQuery = path.join(skillRoot, 'scripts', 'offline-data-query');
const defaultConfigFile = path.join(skillRoot, 'scripts', 'offline-data-query.config.json');

function requireConfig() {
  if (!fs.existsSync(defaultConfigFile) && !process.env.OFFLINE_DATA_QUERY_CONFIG_FILE) {
    assert.fail('offline data query config missing; create scripts/offline-data-query.config.json or set OFFLINE_DATA_QUERY_CONFIG_FILE, then rerun npm run test:live');
  }
}

function readConfig() {
  requireConfig();
  const configFile = process.env.OFFLINE_DATA_QUERY_CONFIG_FILE || defaultConfigFile;
  return JSON.parse(fs.readFileSync(configFile, 'utf8'));
}

function runOfflineProfile(profile, args, options = {}) {
  requireConfig();
  return spawnSync(offlineDataQuery, [
    '--profile', profile,
    '--connect-timeout-ms', '5000',
    '--query-timeout-ms', '10000',
    ...args,
  ], {
    cwd: skillRoot,
    encoding: 'utf8',
    timeout: 20000,
    input: options.input,
  });
}

function runOfflineSource(profileName, args, options = {}) {
  const config = readConfig();
  const profile = config.profiles && config.profiles[profileName];
  assert.ok(profile, `${profileName} profile missing`);
  const sourceArgs = [
    '--source', profile.source,
    '--url', profile.url,
    '--connect-timeout-ms', '5000',
    '--query-timeout-ms', '10000',
  ];
  if (profile.user) sourceArgs.push('--user', profile.user);
  if (profile.password) sourceArgs.push('--password', profile.password);
  return spawnSync(offlineDataQuery, [
    ...sourceArgs,
    ...args,
  ], {
    cwd: skillRoot,
    encoding: 'utf8',
    timeout: 20000,
    input: options.input,
  });
}

function runOffline(args, options = {}) {
  return runOfflineProfile('test-mysql', args, options);
}

test('live offline-data-query default profile uses sealed password', () => {
  const config = readConfig();
  const profile = config.profiles && config.profiles['test-mysql'];

  assert.ok(profile, 'test-mysql profile missing');
  assert.equal(profile.source, 'mysql');
  assert.match(profile.password, /^sealed:v1:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$/);
});

test('live offline-data-query lbk-web-admin profiles are ready', () => {
  const config = readConfig();
  const expected = {
    'lbk-web-admin-mysql-marketing': 'mysql',
    'lbk-web-admin-mysql-data-center': 'mysql',
    'lbk-web-admin-redis': 'redis',
    'lbk-web-admin-redis-market': 'redis',
    'lbk-web-admin-mongo': 'mongo',
  };

  for (const [name, source] of Object.entries(expected)) {
    const profile = config.profiles && config.profiles[name];
    assert.ok(profile, `${name} profile missing`);
    assert.equal(profile.source, source, `${name} source`);
    if (profile.password) {
      assert.match(profile.password, /^sealed:v1:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$/);
    }
  }
});

test('live offline-data-query executes default readonly MySQL profile', () => {
  const result = runOffline(['SELECT 1 AS value']);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, '');
  assert.equal(result.stdout.trim(), 'value\n1');
});

test('live offline-data-query executes lbk-web-admin MySQL profiles', () => {
  for (const profile of ['lbk-web-admin-mysql-marketing', 'lbk-web-admin-mysql-data-center']) {
    const result = runOfflineProfile(profile, ['SELECT 1 AS value']);
    assert.equal(result.status, 0, `${profile}\n${result.stderr}`);
    assert.equal(result.stderr, '');
    assert.equal(result.stdout.trim(), 'value\n1');
  }
});

test('live offline-data-query executes lbk-web-admin Redis profiles', () => {
  for (const profile of ['lbk-web-admin-redis', 'lbk-web-admin-redis-market']) {
    const result = runOfflineProfile(profile, ['TYPE __codemao_troubleshoot_live_probe_never__']);
    assert.equal(result.status, 0, `${profile}\n${result.stderr}`);
    assert.equal(result.stderr, '');
    assert.equal(result.stdout.trim(), 'value\nnone');
  }
});

test('live offline-data-query executes lbk-web-admin Mongo profile', () => {
  const result = runOfflineProfile('lbk-web-admin-mongo', ['{"op":"listCollections","limit":5}']);

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, '');
  assert.match(result.stdout, /^name\n/);
});

test('live offline-data-query executes temporary source arguments', () => {
  const mysql = runOfflineSource('lbk-web-admin-mysql-marketing', ['SELECT 1 AS value']);
  assert.equal(mysql.status, 0, mysql.stderr);
  assert.equal(mysql.stdout.trim(), 'value\n1');

  const redis = runOfflineSource('lbk-web-admin-redis', ['TYPE __codemao_troubleshoot_live_probe_never__']);
  assert.equal(redis.status, 0, redis.stderr);
  assert.equal(redis.stdout.trim(), 'value\nnone');

  const mongo = runOfflineSource('lbk-web-admin-mongo', ['{"op":"listCollections","limit":5}']);
  assert.equal(mongo.status, 0, mongo.stderr);
  assert.match(mongo.stdout, /^name\n/);
});

test('live offline-data-query accepts stdin SQL through public CLI', () => {
  const result = runOffline([], { input: 'SELECT 1 AS value\n' });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, '');
  assert.equal(result.stdout.trim(), 'value\n1');
});

test('live offline-data-query rejects writes before connecting', () => {
  const result = runOffline(['DELETE FROM tbl_xxx']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[readonly_only\]/);
  assert.equal(result.stdout, '');
});
