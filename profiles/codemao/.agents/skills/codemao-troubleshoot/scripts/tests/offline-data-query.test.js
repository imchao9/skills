const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { sealCredential } = require('../skillctl');
const { formatRedisResult, formatRows, resolveMysqlOptions } = require('../offline-data-query');

const skillRoot = path.resolve(__dirname, '..', '..');
const offlineDataQuery = path.join(skillRoot, 'scripts', 'offline-data-query');

function runCli(args, options = {}) {
  return spawnSync(offlineDataQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    input: options.input || '',
    env: {
      ...process.env,
      ...(options.env || {}),
    },
  });
}

function tempConfig(config) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'offline-data-query-test-'));
  const file = path.join(dir, 'config.json');
  fs.writeFileSync(file, `${JSON.stringify(config, null, 2)}\n`);
  return file;
}

function profileConfig(profile = {}) {
  return tempConfig({
    profiles: {
      demo: {
        source: 'mysql',
        url: 'mysql://localhost:3306/demo',
        user: 'readonly_user',
        password: sealCredential('secret-password'),
        ...profile,
      },
    },
  });
}

function redisProfileConfig(profile = {}) {
  return tempConfig({
    profiles: {
      demo: {
        source: 'redis',
        url: 'redis://localhost:6379/0',
        password: sealCredential('redis-password'),
        ...profile,
      },
    },
  });
}

function mongoProfileConfig(profile = {}) {
  return tempConfig({
    profiles: {
      demo: {
        source: 'mongo',
        url: 'mongodb://localhost:27017/demo',
        user: 'readonly_user',
        password: sealCredential('mongo-password'),
        ...profile,
      },
    },
  });
}

test('offline-data-query truncates MySQL output after 1000 rows and reports the full count', () => {
  const rows = Array.from({ length: 1001 }, (_, index) => ({ id: index }));

  const lines = formatRows([{ name: 'id' }], rows).trimEnd().split('\n');

  assert.equal(lines.length, 1002);
  assert.equal(lines[0], 'id');
  assert.equal(lines[1000], '999');
  assert.equal(lines[1001], '[truncated: showing first 1000 of 1001 items]');
  assert.doesNotMatch(lines.join('\n'), /^1000$/m);
});

test('offline-data-query keeps complete MySQL output at the 1000 row boundary', () => {
  const rows = Array.from({ length: 1000 }, (_, index) => ({ id: index }));

  const output = formatRows([{ name: 'id' }], rows);

  assert.equal(output.trimEnd().split('\n').length, 1001);
  assert.match(output, /\n999\n$/);
  assert.doesNotMatch(output, /\[truncated:/);
});

test('offline-data-query truncates Redis arrays after 1000 items and reports the full count', () => {
  const values = Array.from({ length: 1001 }, (_, index) => `value-${index}`);

  const lines = formatRedisResult(values).trimEnd().split('\n');

  assert.equal(lines.length, 1002);
  assert.equal(lines[0], 'index\tvalue');
  assert.equal(lines[1000], '999\tvalue-999');
  assert.equal(lines[1001], '[truncated: showing first 1000 of 1001 items]');
  assert.doesNotMatch(lines.join('\n'), /^1000\t/m);
});

test('offline-data-query truncates Redis objects after 1000 entries and preserves entry order', () => {
  const value = Object.fromEntries(Array.from({ length: 1001 }, (_, index) => [`key-${index}`, `value-${index}`]));

  const lines = formatRedisResult(value).trimEnd().split('\n');

  assert.equal(lines.length, 1002);
  assert.equal(lines[0], 'key\tvalue');
  assert.equal(lines[1000], 'key-999\tvalue-999');
  assert.equal(lines[1001], '[truncated: showing first 1000 of 1001 items]');
  assert.doesNotMatch(lines.join('\n'), /^key-1000\t/m);
});

test('offline-data-query keeps Redis and Mongo distinct array output complete at the 1000 item boundary', () => {
  const values = Array.from({ length: 1000 }, (_, index) => `value-${index}`);

  const output = formatRedisResult(values);

  assert.match(output, /\n999\tvalue-999\n$/);
  assert.doesNotMatch(output, /\[truncated:/);
});

test('offline-data-query keeps Redis object output complete at the 1000 entry boundary', () => {
  const value = Object.fromEntries(Array.from({ length: 1000 }, (_, index) => [`key-${index}`, `value-${index}`]));

  const output = formatRedisResult(value);

  assert.match(output, /\nkey-999\tvalue-999\n$/);
  assert.doesNotMatch(output, /\[truncated:/);
});

test('offline-data-query does not enable MySQL TLS when useSSL is absent', () => {
  const options = resolveMysqlOptions({
    url: 'mysql://localhost:3306/demo',
    user: 'readonly_user',
    password: sealCredential('secret-password'),
  }, { connectTimeoutMs: 5000 });

  assert.equal(Object.hasOwn(options, 'ssl'), false);
});

test('offline-data-query does not enable MySQL TLS when useSSL is false', () => {
  const options = resolveMysqlOptions({
    url: 'mysql://localhost:3306/demo?useSSL=false',
    user: 'readonly_user',
    password: sealCredential('secret-password'),
  }, { connectTimeoutMs: 5000 });

  assert.equal(Object.hasOwn(options, 'ssl'), false);
});

test('offline-data-query enables certificate-verified MySQL TLS when useSSL is true', () => {
  const options = resolveMysqlOptions({
    url: 'mysql://localhost:3306/demo?useSSL=true',
    user: 'readonly_user',
    password: sealCredential('secret-password'),
  }, { connectTimeoutMs: 5000 });

  assert.deepEqual(options.ssl, { rejectUnauthorized: true });
});

test('offline-data-query rejects unsupported non-empty MySQL useSSL values', () => {
  assert.throws(
    () => resolveMysqlOptions({
      url: 'mysql://localhost:3306/demo?useSSL=required',
      user: 'readonly_user',
      password: sealCredential('secret-password'),
    }, { connectTimeoutMs: 5000 }),
    (error) => error.code === 'invalid_config' && /useSSL/.test(error.message),
  );
});

test('offline-data-query help exposes profile interface and not env routing', () => {
  const result = runCli(['--help']);

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /offline-data-query/);
  assert.match(result.stdout, /--profile PROFILE/);
  assert.match(result.stdout, /--source mysql\|redis\|mongo/);
  assert.doesNotMatch(result.stdout, /--env/);
  assert.doesNotMatch(result.stdout, /\bdev\b/);
});

test('offline-data-query rejects unsupported options generically', () => {
  const result = runCli(['--env', 'test', 'SELECT 1']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_argument/);
  assert.match(result.stderr, /--env/);
});

test('offline-data-query requires profile or source', () => {
  const result = runCli(['SELECT 1']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /target_missing/);
});

test('offline-data-query rejects profile and source together', () => {
  const result = runCli(['--profile', 'demo', '--source', 'mysql', 'SELECT 1']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /target_conflict/);
});

test('offline-data-query reports missing config before querying', () => {
  const result = runCli(['--profile', 'demo', 'SELECT 1'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: path.join(os.tmpdir(), 'missing-offline-data-query-config.json') },
  });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /config_missing/);
});

test('offline-data-query reports unknown profile', () => {
  const configFile = tempConfig({ profiles: {} });
  const result = runCli(['--profile', 'missing', 'SELECT 1'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /profile_not_found/);
});

test('offline-data-query rejects unsupported profile source', () => {
  const configFile = profileConfig({ source: 'elasticsearch' });
  const result = runCli(['--profile', 'demo', 'SELECT 1'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_source/);
});

test('offline-data-query validates profile schema', () => {
  const configFile = profileConfig({ url: '' });
  const result = runCli(['--profile', 'demo', 'SELECT 1'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /invalid_config/);
  assert.match(result.stderr, /url/);
});

test('offline-data-query rejects plaintext profile passwords', () => {
  const configFile = profileConfig({ password: 'plain-secret' });
  const result = runCli(['--profile', 'demo', 'SELECT 1'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /plaintext_password_forbidden/);
  assert.match(result.stderr, /credential seal/);
});

test('offline-data-query rejects URL userinfo credentials', () => {
  for (const [configFile, query] of [
    [profileConfig({ url: 'jdbc:mysql://user:secret@localhost:3306/demo' }), 'SELECT 1'],
    [redisProfileConfig({ url: 'redis://:secret@localhost:6379/0' }), 'TYPE key'],
    [mongoProfileConfig({ url: 'mongodb://user:secret@localhost:27017/demo', user: undefined, password: undefined }), '{"op":"listCollections","limit":1}'],
  ]) {
    const result = runCli(['--profile', 'demo', query], {
      env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
    });

    assert.equal(result.status, 2);
    assert.match(result.stderr, /url_userinfo_forbidden/);
  }
});

test('offline-data-query accepts redis profile without mysql-only fields', () => {
  const configFile = redisProfileConfig({ password: undefined });
  const result = runCli(['--profile', 'demo', 'SET key value'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
  assert.doesNotMatch(result.stderr, /user|password/);
});

test('offline-data-query rejects plaintext cli password', () => {
  const result = runCli([
    '--source', 'mysql',
    '--url', 'mysql://127.0.0.1:1/demo',
    '--user', 'readonly_user',
    '--password', 'plain-secret',
    'SELECT 1',
  ]);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /plaintext_password_forbidden/);
});

test('offline-data-query routes mysql source arguments after validation', () => {
  const result = runCli([
    '--source', 'mysql',
    '--url', 'mysql://127.0.0.1:1/demo',
    '--user', 'readonly_user',
    '--password', sealCredential('mysql-password'),
    '--connect-timeout-ms', '100',
    'SELECT 1',
  ]);

  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stderr, /target_missing|invalid_config|readonly_only|plaintext_password_forbidden/);
  assert.match(result.stderr, /connect_failed|driver_missing/);
});

test('offline-data-query routes redis source without password', () => {
  const result = runCli([
    '--source', 'redis',
    '--url', 'redis://127.0.0.1:1/0',
    '--connect-timeout-ms', '100',
    'TYPE missing_key',
  ]);

  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stderr, /target_missing|invalid_config|readonly_only|password/);
  assert.match(result.stderr, /connect_failed|driver_missing/);
});

test('offline-data-query routes mongo source arguments after validation', () => {
  const result = runCli([
    '--source', 'mongo',
    '--url', 'mongodb://127.0.0.1:1/demo',
    '--user', 'readonly_user',
    '--password', sealCredential('mongo-password'),
    '--connect-timeout-ms', '100',
    '{"op":"listCollections","limit":1}',
  ]);

  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stderr, /target_missing|invalid_config|readonly_only|plaintext_password_forbidden/);
  assert.match(result.stderr, /connect_failed|driver_missing/);
});

test('offline-data-query rejects redis write commands before driver use', () => {
  const configFile = redisProfileConfig();
  const result = runCli(['--profile', 'demo', 'SET key value'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
});

test('offline-data-query routes redis readonly commands after source detection', () => {
  const configFile = redisProfileConfig({ url: 'redis://127.0.0.1:1/0' });
  const result = runCli(['--profile', 'demo', '--connect-timeout-ms', '100', 'TYPE missing_key'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stderr, /readonly_only|unsupported_source|invalid_config/);
  assert.match(result.stderr, /connect_failed|driver_missing/);
});

test('offline-data-query rejects mongo write operations before driver use', () => {
  const configFile = mongoProfileConfig();
  const result = runCli(['--profile', 'demo', '{"op":"insertOne","collection":"demo","document":{"x":1}}'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
});

test('offline-data-query routes mongo readonly operations after source detection', () => {
  const configFile = mongoProfileConfig({ url: 'mongodb://127.0.0.1:1/demo' });
  const result = runCli(['--profile', 'demo', '--connect-timeout-ms', '100', '{"op":"listCollections","limit":1}'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stderr, /readonly_only|unsupported_source|invalid_config/);
  assert.match(result.stderr, /connect_failed|driver_missing/);
});

test('offline-data-query rejects non-read-only SQL before driver use', () => {
  const configFile = profileConfig();
  const result = runCli(['--profile', 'demo', 'DELETE FROM tbl_xxx'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
});

test('offline-data-query rejects multiple SQL statements', () => {
  const configFile = profileConfig();
  const result = runCli(['--profile', 'demo', 'SELECT 1; SELECT 2'], {
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /multi_statement_unsupported/);
});

test('offline-data-query applies readonly checks to stdin SQL', () => {
  const configFile = profileConfig();
  const result = runCli(['--profile', 'demo'], {
    input: 'UPDATE tbl_xxx SET name = 1',
    env: { OFFLINE_DATA_QUERY_CONFIG_FILE: configFile },
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
});
