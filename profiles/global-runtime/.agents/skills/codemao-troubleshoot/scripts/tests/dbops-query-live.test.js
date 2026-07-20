const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const dbopsQuery = path.join(skillRoot, 'scripts', 'dbops-query');
const defaultCookieFile = path.join(skillRoot, 'output', 'dbops-auth-cookie.txt');
const dbopsModule = require('../dbops-query');
const authLiveEnabled = process.env.CODEMAO_AUTH_LIVE === '1';

function hasCookie() {
  if (process.env.DBOPS_COOKIE && process.env.DBOPS_COOKIE.trim()) return true;
  const cookieFile = process.env.DBOPS_COOKIE_FILE || defaultCookieFile;
  return fs.existsSync(cookieFile) && dbopsModule.readCookieFromFile(cookieFile);
}

function runDbops(args) {
  const result = spawnSync(dbopsQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function runDbopsText(args) {
  const result = spawnSync(dbopsQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function runDbopsProcess(args) {
  return spawnSync(dbopsQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    timeout: 30000,
  });
}

function requireCookie() {
  if (!hasCookie()) {
    assert.fail('dbops cookie missing; run scripts/dbops-query auth, then rerun npm run test:live');
  }
}

function authDbops() {
  return new Promise((resolve, reject) => {
    const child = spawn(dbopsQuery, ['auth'], {
      cwd: skillRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    const started = Date.now();
    const lines = [];
    let stdout = '';
    let stderr = '';
    let authOkAt = 0;
    const timeout = setTimeout(() => {
      child.kill('SIGTERM');
      reject(new Error('dbops auth timed out; complete browser login or rerun scripts/dbops-query auth manually'));
    }, 240000);

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
      for (const line of chunk.split(/\r?\n/).filter(Boolean)) {
        lines.push(line);
        if (line.includes('"auth-ok"')) authOkAt = Date.now();
      }
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.on('close', (status) => {
      clearTimeout(timeout);
      resolve({ status, stdout, stderr, lines, started, authOkAt, closedAt: Date.now() });
    });
  });
}

function isLowCostReadonlySql(sql) {
  const normalized = String(sql || '').trim().replace(/\s+/g, ' ').toLowerCase();
  if (/^select\s+(1|version\s*\()/i.test(normalized)) return true;
  if (/^(show|desc|describe|explain)\b/i.test(normalized)) return true;
  if (/^select\b/i.test(normalized) && /\blimit\s+\d+\b/i.test(normalized)) return true;
  return false;
}

function pickRecentQueryableLog() {
  const querylog = runDbops(['querylog', 'limit=10', 'offset=0']);
  assert.equal(querylog.http_status, undefined);
  const rows = querylog.items || [];
  for (const row of rows) {
    if (!row.id) continue;
    const info = runDbops(['queryloginfo', String(row.id)]);
    const detail = info.items && info.items[0];
    if (!detail || !detail.instance_name || !detail.db_name || !detail.sql) continue;
    if (isLowCostReadonlySql(detail.sql)) return { ...detail, sqllog: detail.sql };
  }
  assert.fail('no low-cost readonly querylog row found; run a safe dbops query such as SELECT version() first, then rerun npm run test:live');
}

if (authLiveEnabled) {
  test('auth-live dbops-query auth captures cookie with compact output', { timeout: 260000 }, async () => {
    const result = await authDbops();

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.lines.map((line) => JSON.parse(line).step), ['auth-opened', 'auth-ok']);
    assert.doesNotMatch(result.stdout, /cookie_count|timeout|https?:\/\/|sessionid|csrftoken|authorization/i);
    assert.ok(result.authOkAt > 0, 'auth-ok line was not printed');
    assert.ok(result.closedAt - result.authOkAt < 3000, `auth process exited slowly after auth-ok: ${result.closedAt - result.authOkAt}ms`);
    assert.ok(hasCookie(), 'dbops auth did not write a usable cookie');

    const instances = runDbops(['instances', 'can_read']);
    assert.equal(instances.http_status, undefined);
    assert.equal(Array.isArray(instances.items), true);
  });
}

test('live dbops-query read-only platform checks', () => {
  requireCookie();

  const instances = runDbops(['instances', 'can_read']);
  assert.equal(instances.http_status, undefined);
  assert.equal(instances.payload, undefined);
  assert.equal(typeof instances.count, 'number');
  assert.equal(Array.isArray(instances.items), true);

  const querylog = runDbops(['querylog', 'limit=1', 'offset=0']);
  assert.equal(querylog.http_status, undefined);
  assert.equal(querylog.payload, undefined);
  assert.equal(typeof querylog.total, 'number');
  assert.equal(Array.isArray(querylog.items), true);
});

test('live dbops-query resources and raw api stay read-only', () => {
  requireCookie();

  const instances = runDbops(['instances', 'can_read']);
  const candidate = instances.items.find((item) => item.db_type === 'mysql') || instances.items[0];
  assert.ok(candidate && candidate.instance_name, 'no dbops instance available');

  const resources = runDbops(['resources', candidate.instance_name, 'database']);
  assert.equal(resources.http_status, undefined);
  assert.equal(resources.payload, undefined);
  assert.equal(Array.isArray(resources.items), true);

  const api = runDbops(['api', 'GET', '/group/user_all_instances/', 'tag_codes[]=can_read']);
  assert.equal(api.http_status, 200);
  assert.equal(typeof api.payload, 'object');
  assert.equal(Object.prototype.hasOwnProperty.call(api.payload, 'data'), true);
});

test('live dbops-query queryloginfo follows a real querylog row', () => {
  requireCookie();

  const querylog = runDbops(['querylog', 'limit=1', 'offset=0']);
  assert.equal(querylog.http_status, undefined);
  const row = querylog.items && querylog.items[0];
  assert.ok(row && row.id, 'querylog returned no rows');

  const info = runDbops(['queryloginfo', String(row.id)]);
  assert.equal(info.http_status, undefined);
  assert.equal(Array.isArray(info.items), true);
  assert.ok(info.items.length >= 1);
  assert.equal(String(info.items[0].id), String(row.id));
  assert.doesNotMatch(JSON.stringify(info), /sessionid|csrftoken|authorization/i);
});

test('live dbops-query query-on can execute a recent low-cost SQL log', () => {
  requireCookie();

  const detail = pickRecentQueryableLog();
  const result = runDbopsProcess(['query-on', detail.instance_name, detail.db_name, detail.sqllog]);
  assert.equal(result.status, 0, result.stderr);
  assert.ok(result.stdout.trim().length > 0);
  assert.doesNotMatch(result.stdout, /sessionid|csrftoken|authorization/i);
  assert.doesNotMatch(result.stderr, /sessionid|csrftoken|authorization/i);
});

test('live dbops-query favorites are discoverable without printing cookie material', () => {
  requireCookie();

  const output = runDbops(['favorite-list']);
  assert.equal(output.http_status, undefined);
  assert.equal(Array.isArray(output.items), true);
  assert.doesNotMatch(JSON.stringify(output), /sessionid|csrftoken|authorization/i);
  if (output.items.length) {
    const alias = output.items[0].alias.slice(0, 2);
    const foundText = runDbopsText(['favorite-find', alias]);
    const found = JSON.parse(foundText);
    assert.equal(found.content_type, undefined);
    assert.equal(Array.isArray(found.items), true);
    assert.ok(found.items.length >= 1);
    assert.doesNotMatch(foundText, /sessionid|csrftoken|authorization/i);
  }
});

test('live dbops-query favorite-info verifies table evidence without running favorite SQL', () => {
  requireCookie();

  const output = runDbops(['favorite-list']);
  assert.ok(output.items.length >= 1, 'favorite list is empty');
  const info = runDbops(['favorite-info', output.items[0].alias]);

  assert.equal(typeof info.alias, 'string');
  assert.equal(typeof info.query_log_id, 'string');
  assert.equal(typeof info.instance_name, 'string');
  assert.equal(typeof info.db_name, 'string');
  assert.equal(typeof info.sql, 'string');
  assert.equal(typeof info.resource, 'object');
  assert.doesNotMatch(JSON.stringify(info), /sessionid|csrftoken|authorization/i);

  if (info.db_type === 'mysql' && info.db_name) {
    const tables = runDbops(['resources', info.instance_name, 'table', `db_name=${info.db_name}`]);
    assert.equal(tables.http_status, undefined);
    assert.equal(Array.isArray(tables.items), true);
  }
});
