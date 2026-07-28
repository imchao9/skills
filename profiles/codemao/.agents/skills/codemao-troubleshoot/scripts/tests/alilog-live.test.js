const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const alilog = path.join(skillRoot, 'scripts', 'alilog');
const {
  parseArgs,
  applyUserConfig,
  newBrowserContext,
  disposeBrowserSession,
  openLoginPage,
  runAliyunLoginAutomation,
  readPasswordFromKeychain,
  runAuth,
} = require('../alilog');
const authFile = path.join(skillRoot, 'output', 'alilog-auth.json');
const authLiveEnabled = process.env.CODEMAO_AUTH_LIVE === '1';
const negativeAuthLiveEnabled = authLiveEnabled
  && process.env.CODEMAO_ALILOG_NEGATIVE_AUTH_LIVE === '1';
const interactiveAuthLiveEnabled = authLiveEnabled
  && process.env.CODEMAO_ALILOG_INTERACTIVE_AUTH_LIVE === '1';

async function withEnvironmentVariableUnset(name, operation) {
  const originalValue = process.env[name];
  delete process.env[name];
  try {
    return await operation();
  } finally {
    if (originalValue === undefined) delete process.env[name];
    else process.env[name] = originalValue;
  }
}

async function parseKeychainAuthArgs() {
  const args = parseArgs(['auth', '--timeout', '90']);
  args.debug = true;
  args.userFile = path.join(os.tmpdir(), `alilog-negative-auth-live-${crypto.randomUUID()}.json`);
  await withEnvironmentVariableUnset('ALILOG_USERNAME', () => applyUserConfig(args));
  assert.ok(args.username, 'Keychain account is required for negative auth live tests');
  return args;
}

function randomBase32Seed() {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  return Array.from(crypto.randomBytes(20), (value) => alphabet[value & 31]).join('');
}

async function observeSingleAliyunLoginRejection(args, autoFillPlan) {
  let browser;
  const debugLogs = [];
  const originalConsoleLog = console.log;
  try {
    browser = await newBrowserContext(args, true);
    const page = browser.context.pages()[0] || await browser.context.newPage();
    console.log = (...values) => debugLogs.push(values.map(String).join(' '));
    await openLoginPage(page, browser.context, args);
    let rejection;
    try {
      await runAliyunLoginAutomation(page, args, { autoFillPlan });
    } catch (error) {
      rejection = error;
    }
    return { debugLogs, rejection };
  } finally {
    console.log = originalConsoleLog;
    await disposeBrowserSession(browser);
  }
}

function assertNegativeAuthDebug(debugLogs, secrets, expectedActions) {
  const output = debugLogs.join('\n');
  for (const [action, expectedCount] of Object.entries(expectedActions)) {
    const actualCount = debugLogs.filter((line) => line.includes(`auto-login clicked ${action}`)).length;
    assert.equal(actualCount, expectedCount, action);
  }
  for (const secret of secrets) {
    assert.equal(output.includes(secret), false, 'debug output exposed an in-memory credential');
  }
  assert.doesNotMatch(output, /cookie|csrf|authorization|requestid/i);
}

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

function runAlilogIndexFields(logstore) {
  return runAlilogCommand('index-fields', {
    project: 'kuebernetes-production',
    logstore,
  }, []);
}

function assertCompactedObjectProperties(value) {
  if (Array.isArray(value)) {
    for (const child of value) assertCompactedObjectProperties(child);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const child of Object.values(value)) {
    assert.notStrictEqual(child, '');
    assert.notStrictEqual(child, null);
    assertCompactedObjectProperties(child);
  }
}

function assertLiveIndexFields(logstore) {
  const result = runAlilogIndexFields(logstore);
  const text = result.stdout.trim();
  const output = JSON.parse(text);

  assert.equal(result.stderr, '', logstore);
  assert.equal(text.split('\n').length, 1, logstore);
  assert.ok(output && typeof output === 'object' && !Array.isArray(output), logstore);
  assert.ok(Object.keys(output).length > 0, logstore);
  for (const key of [
    'project', 'logstore', 'ProjectName', 'LogStoreName',
    'code', 'success', 'message', 'requestId',
    'storage', 'log_reduce', 'log_reduce_white_list', 'log_reduce_black_list',
  ]) {
    assert.equal(Object.hasOwn(output, key), false, `${logstore}: ${key}`);
  }
  assertCompactedObjectProperties(output);
  assert.doesNotMatch(text, /cookie|csrf|authorization/i, logstore);
}

async function authAlilog(argv = ['auth', '--timeout', '240']) {
  const args = parseArgs(argv);
  args.debug = true;
  await applyUserConfig(args);
  const output = [];
  await runAuth(args, {
    writeStdoutLine: async (line) => output.push(line),
  });
  return output;
}

function assertAuthReadyAndQueryWorks(output) {
  assert.deepStrictEqual(output, ['auth ready']);
  assert.doesNotMatch(output.join('\n'), /cookie|csrf|x-csrf|https?:\/\//i);
  assert.ok(fs.existsSync(authFile), 'alilog auth did not write auth file');
  assert.equal(fs.statSync(authFile).mode & 0o777, 0o600, 'alilog auth file must be mode 0600');

  const query = runAlilog([
    '--query', '* and _container_name_:__codemao_troubleshoot_live_probe_never__',
    '--time', 'last_5m',
    '--size', '1',
  ]);
  assert.ok(query.stdout.trim().length > 0);
  assert.doesNotMatch(query.stdout, /cookie|csrf|x-csrf/i);
}

async function removeInteractiveProfile(profileDir) {
  const deadline = Date.now() + 10000;
  while (true) {
    try {
      fs.rmSync(profileDir, { recursive: true, force: true });
      return;
    } catch (error) {
      if (Date.now() >= deadline) throw error;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
}

if (negativeAuthLiveEnabled) {
  test('auth-live alilog live server rejection DOM reports password_rejected without retry', { timeout: 100000 }, async () => {
    const args = await parseKeychainAuthArgs();
    const wrongPassword = `invalid-${crypto.randomBytes(24).toString('base64url')}`;
    const randomSeed = randomBase32Seed();

    const { debugLogs, rejection } = await observeSingleAliyunLoginRejection(args, {
      username: args.username,
      password: wrongPassword,
      totpSeed: randomSeed,
    });

    assert.equal(rejection && rejection.message, 'Aliyun auto-login stopped: password_rejected');
    assertNegativeAuthDebug(debugLogs, [args.username, wrongPassword, randomSeed], {
      'password-submit': 1,
      'totp-submit': 0,
    });
  });

  test('auth-live alilog live server rejection DOM reports totp_rejected without retry', { timeout: 100000 }, async () => {
    const args = await parseKeychainAuthArgs();
    const password = await withEnvironmentVariableUnset(
      'ALILOG_PASSWORD',
      () => readPasswordFromKeychain(args),
    );
    const wrongSeed = randomBase32Seed();

    const { debugLogs, rejection } = await observeSingleAliyunLoginRejection(args, {
      username: args.username,
      password,
      totpSeed: wrongSeed,
    });

    assert.equal(rejection && rejection.message, 'Aliyun auto-login stopped: totp_rejected');
    assertNegativeAuthDebug(debugLogs, [args.username, password, wrongSeed], {
      'password-submit': 1,
      'totp-submit': 1,
    });
  });
}

if (authLiveEnabled) {
  test('auth-live alilog auth refreshes captured auth and query works', { timeout: 280000 }, async () => {
    const output = await authAlilog();

    assertAuthReadyAndQueryWorks(output);
  });
}

if (interactiveAuthLiveEnabled) {
  test('auth-live alilog headed auto-fill with explicit profile refreshes auth and query works', { timeout: 300000 }, async () => {
    const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'alilog-auth-live-auto-fill-'));
    try {
      const output = await authAlilog([
        'auth',
        '--timeout', '240',
        '--profile-dir', profileDir,
      ]);

      assertAuthReadyAndQueryWorks(output);
      assert.ok(fs.existsSync(profileDir), 'alilog must preserve an explicit browser profile');
    } finally {
      await removeInteractiveProfile(profileDir);
    }
  });

  test('auth-live alilog headed manual login refreshes auth and query works', { timeout: 300000 }, async () => {
    const output = await authAlilog([
      'auth',
      '--timeout', '240',
      '--no-auto-fill',
    ]);

    assertAuthReadyAndQueryWorks(output);
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

test('live alilog production index-fields returns current compact index configuration', () => {
  assertLiveIndexFields('production');
});

test('live alilog nginx-ingress index-fields returns current compact index configuration', () => {
  assertLiveIndexFields('nginx-ingress');
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
