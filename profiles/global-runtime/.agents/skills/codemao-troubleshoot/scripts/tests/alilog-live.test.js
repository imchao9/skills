const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const alilog = path.join(skillRoot, 'scripts', 'alilog');
const authFile = path.join(skillRoot, 'output', 'alilog-auth.json');
const authLiveEnabled = process.env.CODEMAO_AUTH_LIVE === '1';

function requireAuthFile() {
  if (!fs.existsSync(authFile)) {
    assert.fail('SLS auth missing; run scripts/alilog auth, then rerun npm run test:live');
  }
}

function runAlilogCommand(command, target, args) {
  requireAuthFile();
  const result = spawnSync(alilog, [
    command,
    '--project', target.project,
    ...(target.logstore ? ['--logstore', target.logstore] : []),
    ...args,
  ], {
    cwd: skillRoot,
    encoding: 'utf8',
    timeout: 30000,
  });
  assert.equal(result.status, 0, result.stderr);
  return result;
}

function runAlilogTarget(target, args) {
  return runAlilogCommand('query', target, args);
}

function runAlilog(args) {
  return runAlilogTarget({ project: 'kuebernetes-production', logstore: 'production' }, args);
}

function runAlilogFields(args) {
  return runAlilogCommand('fields', { project: 'kuebernetes-production', logstore: 'production' }, args);
}

function runAlilogLogstores(args) {
  return runAlilogCommand('logstores', { project: 'kuebernetes-production' }, args);
}

function authAlilog() {
  return new Promise((resolve, reject) => {
    const child = spawn(alilog, ['auth', '--timeout', '240'], {
      cwd: skillRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let readyAt = 0;
    const timeout = setTimeout(() => {
      child.kill('SIGTERM');
      reject(new Error('alilog auth timed out; complete browser login or rerun scripts/alilog auth manually'));
    }, 260000);

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
      if (chunk.includes('auth ready')) readyAt = Date.now();
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
      resolve({ status, stdout, stderr, readyAt, closedAt: Date.now() });
    });
  });
}

if (authLiveEnabled) {
  test('auth-live alilog auth refreshes captured auth and query works', { timeout: 280000 }, async () => {
    const result = await authAlilog();

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), 'auth ready');
    assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf|https?:\/\//i);
    assert.ok(result.readyAt > 0, 'auth ready line was not printed');
    assert.ok(fs.existsSync(authFile), 'alilog auth did not write auth file');

    const query = runAlilog([
      '--query', '* and _container_name_:__codemao_troubleshoot_live_probe_never__',
      '--time', 'last_5m',
      '--size', '1',
    ]);
    assert.ok(query.stdout.trim().length > 0);
    assert.doesNotMatch(query.stdout, /cookie|csrf|x-csrf/i);
  });
}

test('live alilog query uses captured auth and compact output', () => {
  const result = runAlilog([
    '--query', '* and _container_name_:__codemao_troubleshoot_live_probe_never__',
    '--time', 'last_5m',
    '--size', '1',
  ]);

  assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf/i);
  assert.doesNotMatch(result.stdout, /query failed/);
  assert.ok(result.stdout.trim().length > 0);
  assert.ok(result.stdout.length < 2200);
});

test('live alilog query supports selected fields without leaking auth', () => {
  const result = runAlilog([
    '--query', '* and _container_name_:__codemao_troubleshoot_live_probe_never__',
    '--time', 'last_5m',
    '--size', '1',
    '--select-fields', '__time__,_container_name_',
  ]);

  assert.equal(result.stderr, '');
  assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf/i);
  assert.ok(result.stdout.trim().length > 0);
  assert.ok(result.stdout.length < 2200);
});

test('live alilog raw argument stays unsupported', () => {
  const result = spawnSync(alilog, [
    'query',
    '--project', 'kuebernetes-production',
    '--logstore', 'production',
    '--query', '* and _container_name_:__codemao_troubleshoot_live_probe_never__',
    '--time', 'last_5m',
    '--size', '1',
    '--raw',
  ], {
    cwd: skillRoot,
    encoding: 'utf8',
    timeout: 30000,
  });

  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unknown argument: --raw/);
  assert.equal(result.stdout, '');
});

test('live alilog aggregation output stays compact and readable', () => {
  const result = runAlilog([
    '--query', '_container_name_: lbk-web-admin | SELECT count(*) AS cnt',
    '--time', 'last_15m',
    '--size', '10',
  ]);

  assert.equal(result.stderr, '');
  assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf/i);
  assert.doesNotMatch(result.stdout, /query failed/);
  assert.match(result.stdout, /result=cnt=\d+/);
  assert.ok(result.stdout.length < 1000);
});

test('live alilog fields returns compact field list', () => {
  const result = runAlilogFields([
    '--query', '*',
    '--time', 'last_15m',
  ]);
  const output = JSON.parse(result.stdout);

  assert.equal(result.stderr, '');
  assert.equal(typeof output.sampled_logs, 'number');
  assert.equal(typeof output.count, 'number');
  assert.equal(Array.isArray(output.fields), true);
  assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf|authorization/i);
  assert.ok(result.stdout.length < 4000);
});

test('live alilog logstores can search by keyword with compact pagination', () => {
  const result = runAlilogLogstores([
    '--keyword', 'nginx',
    '--page-size', '18',
  ]);
  const output = JSON.parse(result.stdout);

  assert.equal(result.stderr, '');
  assert.equal(typeof output.total, 'number');
  assert.equal(output.page, 1);
  assert.equal(output.page_size, 18);
  assert.ok(output.next_page === null || typeof output.next_page === 'number');
  assert.equal(Array.isArray(output.logstores), true);
  assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf|authorization/i);
  assert.ok(output.logstores.some((name) => /nginx/i.test(name)));
});

test('live alilog infrastructure logstores get compact field fallback', () => {
  for (const logstore of ['nginx-ingress', 'nginx-ingress-user', 'tomcat-log']) {
    const result = runAlilogTarget({ project: 'kuebernetes-production', logstore }, [
      '--query', '*',
      '--time', 'last_30m',
      '--size', '1',
    ]);

    assert.equal(result.stderr, '', logstore);
    assert.doesNotMatch(result.stdout, /cookie|csrf|x-csrf|authorization/i, logstore);
    assert.match(result.stdout, /\[1\]/, logstore);
    assert.match(result.stdout, /\b(message|content|summary)=/, logstore);
    assert.match(result.stdout, /\b(status|method|url|host|request_time)=/, logstore);
    assert.ok(result.stdout.length < 2200, logstore);
  }
});
