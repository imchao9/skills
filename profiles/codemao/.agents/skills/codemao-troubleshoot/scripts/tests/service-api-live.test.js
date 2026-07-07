const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const serviceApi = path.join(skillRoot, 'scripts', 'service-api');
const defaultConfigFile = path.join(skillRoot, 'scripts', 'service-api.config.json');
const defaultAuthFile = path.join(skillRoot, 'output', 'service-api-auth.json');
const liveEnv = process.env.CODEMAO_SERVICE_API_LIVE_ENV || 'test';
const liveKeyword = 'account';
const configFile = process.env.SERVICE_API_CONFIG_FILE || defaultConfigFile;
const authFile = process.env.SERVICE_API_AUTH_FILE || defaultAuthFile;
const authLiveEnabled = process.env.CODEMAO_AUTH_LIVE === '1';

function readConfig() {
  if (!fs.existsSync(configFile)) {
    assert.fail(`service-api config not found: ${configFile}`);
  }
  return JSON.parse(fs.readFileSync(configFile, 'utf8'));
}

function getEnvConfig(config) {
  const envConfig = config[liveEnv];
  if (!envConfig) {
    assert.fail(`service-api env config missing: ${liveEnv}`);
  }
  return envConfig;
}

function readAuthState() {
  if (!fs.existsSync(authFile)) {
    assert.fail(`service-api auth state missing: ${authFile}; run scripts/service-api auth admin --env ${liveEnv}`);
  }
  return JSON.parse(fs.readFileSync(authFile, 'utf8'));
}

function getEnvAuthState(authState) {
  const envAuthState = authState[liveEnv];
  if (!envAuthState) {
    assert.fail(`service-api auth state missing env=${liveEnv}; run scripts/service-api auth admin --env ${liveEnv}`);
  }
  return envAuthState;
}

function runServiceApi(args) {
  const result = spawnSync(serviceApi, ['--config', configFile, ...args], {
    cwd: skillRoot,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function authServiceApi(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(serviceApi, ['--config', configFile, 'auth', ...args], {
      cwd: skillRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    const lines = [];
    let stdout = '';
    let stderr = '';
    let authOkAt = 0;
    const timeout = setTimeout(() => {
      child.kill('SIGTERM');
      reject(new Error('service-api auth timed out; complete browser login or rerun the auth command manually'));
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
      resolve({ status, stdout, stderr, lines, authOkAt, closedAt: Date.now() });
    });
  });
}

function assertCompactSuccess(output) {
  assert.deepEqual(Object.keys(output).sort(), ['body', 'status_code']);
  assert.equal(output.status_code, 200);
}

function assertPageMeta(output) {
  assert.equal(typeof output.total, 'number');
  assert.equal(output.total_count, undefined);
  assert.equal(output.returned_count, undefined);
  assert.equal(output.page, 1);
  assert.equal(output.page_size, 5);
  assert.ok(output.next_page === null || typeof output.next_page === 'number');
  assert.equal(Object.prototype.hasOwnProperty.call(output, 'raw'), false);
}

function pickService() {
  const output = runServiceApi([
    'discover',
    'list',
    '--env', liveEnv,
    '--keyword', liveKeyword,
    '--page-size', '5',
  ]);
  assertPageMeta(output);
  assert.ok(Array.isArray(output.services));
  const service = output.services[0] && output.services[0].service;
  if (!service) assert.fail(`no Eureka service matched keyword: ${liveKeyword}`);
  return service;
}

function pickApp() {
  const output = runServiceApi([
    'config',
    'list',
    '--env', liveEnv,
    '--keyword', liveKeyword,
    '--page-size', '5',
  ]);
  assertPageMeta(output);
  assert.ok(Array.isArray(output.apps));
  const app = output.apps[0] && output.apps[0].app_id;
  if (!app) assert.fail(`no Apollo app matched keyword: ${liveKeyword}`);
  return app;
}

function assertAuthOutput(result) {
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.lines.map((line) => JSON.parse(line).step), ['auth-opened', 'auth-ok']);
  assert.doesNotMatch(result.stdout, /cookie|authorization|https?:\/\/|timeout|auth_check/i);
  assert.ok(result.authOkAt > 0, 'auth-ok line was not printed');
  assert.ok(result.closedAt - result.authOkAt < 3000, `auth process exited slowly after auth-ok: ${result.closedAt - result.authOkAt}ms`);
}

if (authLiveEnabled) {
  test('auth-live service-api admin auth updates cookie and request works', { timeout: 260000 }, async () => {
    const config = readConfig();
    const envConfig = getEnvConfig(config);
    if (!envConfig.adminLoginUrl) assert.fail(`adminLoginUrl missing for ${liveEnv}`);
    if (!envConfig.adminAuthCheckUrl) assert.fail(`adminAuthCheckUrl missing for ${liveEnv}`);

    const result = await authServiceApi(['admin', '--env', liveEnv]);
    assertAuthOutput(result);

    const updatedEnvAuthState = getEnvAuthState(readAuthState());
    assert.equal(typeof updatedEnvAuthState.adminCookie, 'string');
    assert.ok(updatedEnvAuthState.adminCookie.trim().length > 0);
    assertCompactSuccess(runServiceApi([
      'request',
      '--env', liveEnv,
      '--url', envConfig.adminAuthCheckUrl,
      '--auth', 'admin',
      '--timeout', '10',
    ]));
  });

  test('auth-live service-api customer auth updates cookie and request works', { timeout: 260000 }, async () => {
    const config = readConfig();
    const envConfig = getEnvConfig(config);
    if (!envConfig.customerLoginUrl) assert.fail(`customerLoginUrl missing for ${liveEnv}`);
    if (!envConfig.customerAuthCheckUrl) assert.fail(`customerAuthCheckUrl missing for ${liveEnv}`);

    const result = await authServiceApi(['customer', '--env', liveEnv]);
    assertAuthOutput(result);

    const updatedEnvAuthState = getEnvAuthState(readAuthState());
    assert.equal(typeof updatedEnvAuthState.customerCookie, 'string');
    assert.ok(updatedEnvAuthState.customerCookie.trim().length > 0);
    assertCompactSuccess(runServiceApi([
      'request',
      '--env', liveEnv,
      '--url', envConfig.customerAuthCheckUrl,
      '--auth', 'customer',
      '--timeout', '10',
    ]));
  });

  test('auth-live service-api custom auth stores origin cookie and request works', { timeout: 260000 }, async () => {
    const config = readConfig();
    const envConfig = getEnvConfig(config);
    if (!envConfig.adminLoginUrl) assert.fail(`adminLoginUrl missing for ${liveEnv}`);
    if (!envConfig.adminAuthCheckUrl) assert.fail(`adminAuthCheckUrl missing for ${liveEnv}`);

    const result = await authServiceApi([
      'custom',
      '--login-url', envConfig.adminLoginUrl,
      '--auth-check-url', envConfig.adminAuthCheckUrl,
    ]);
    assertAuthOutput(result);

    const origin = new URL(envConfig.adminAuthCheckUrl).origin;
    const updatedAuthState = readAuthState();
    const entry = updatedAuthState.customCookies && updatedAuthState.customCookies[origin];
    assert.equal(typeof entry, 'object');
    assert.equal(typeof entry.cookie, 'string');
    assert.ok(entry.cookie.trim().length > 0);
    assert.equal(entry.authCheckUrl, envConfig.adminAuthCheckUrl);
    assertCompactSuccess(runServiceApi([
      'request',
      '--url', envConfig.adminAuthCheckUrl,
      '--auth', 'custom',
      '--timeout', '10',
    ]));
  });
}

test('live service-api discover list and exists keep compact output', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  if (!envConfig.eurekaServerUrl) assert.fail(`eurekaServerUrl missing for ${liveEnv}`);

  const service = pickService();
  const exists = runServiceApi([
    'discover',
    'exists',
    '--env', liveEnv,
    '--service', service,
  ]);
  assert.deepEqual(Object.keys(exists).sort(), [
    'exists',
    'instance_count',
    'url',
  ]);
  assert.equal(exists.exists, true);
  assert.equal(typeof exists.url, 'string');
});

test('live service-api discover get can expose raw data on demand', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  if (!envConfig.eurekaServerUrl) assert.fail(`eurekaServerUrl missing for ${liveEnv}`);

  const service = pickService();
  const output = runServiceApi([
    'discover',
    'get',
    '--env', liveEnv,
    '--service', service,
    '--raw',
  ]);
  assert.equal(output.env, undefined);
  assert.equal(output.service, undefined);
  assert.equal(typeof output.instance_count, 'number');
  assert.ok(output.instance_count >= 1);
  assert.equal(typeof output.url, 'string');
  assert.equal(Array.isArray(output.instances), true);
  assert.equal(typeof output.raw, 'object');
  assert.doesNotMatch(JSON.stringify(output), /cookie|authorization/i);
});

test('live service-api config list and exists keep compact output', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  if (!envConfig.apolloDomain) assert.fail(`apolloDomain missing for ${liveEnv}`);
  if (!envConfig.apolloPortalUrl) assert.fail(`apolloPortalUrl missing for ${liveEnv}`);

  const app = pickApp();
  const exists = runServiceApi([
    'config',
    'exists',
    '--env', liveEnv,
    '--app', app,
  ]);
  assert.deepEqual(Object.keys(exists).sort(), [
    'app',
    'env',
    'exists',
    'namespace',
    'status_code',
  ]);
  assert.equal(exists.exists, true);
  assert.equal(exists.status_code, 200);
});

test('live service-api config get can list keys without full namespace output', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  if (!envConfig.apolloDomain) assert.fail(`apolloDomain missing for ${liveEnv}`);

  const app = pickApp();
  const output = runServiceApi([
    'config',
    'get',
    '--env', liveEnv,
    '--app', app,
    '--namespace', 'application',
    '--keys',
  ]);
  assert.equal(output.env, undefined);
  assert.equal(output.app, undefined);
  assert.equal(output.results, undefined);
  assert.equal(output.headers, undefined);
  assert.equal(Array.isArray(output.application), true);
  assert.ok(output.application.length > 0);
  assert.doesNotMatch(JSON.stringify(output), /cookie|authorization/i);
});

test('live service-api request --auth admin keeps compact output', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  const envAuthState = getEnvAuthState(readAuthState());
  if (!envConfig.adminAuthCheckUrl) assert.fail(`adminAuthCheckUrl missing for ${liveEnv}`);
  if (!envAuthState.adminCookie) assert.fail(`adminCookie missing; run scripts/service-api auth admin --env ${liveEnv}`);

  const output = runServiceApi([
    'request',
    '--env', liveEnv,
    '--url', envConfig.adminAuthCheckUrl,
    '--auth', 'admin',
    '--timeout', '10',
  ]);
  assertCompactSuccess(output);
});

test('live service-api request reaches admin service path with redacted auth diagnostics', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  const envAuthState = getEnvAuthState(readAuthState());
  if (!envAuthState.adminCookie) assert.fail(`adminCookie missing; run scripts/service-api auth admin --env ${liveEnv}`);

  const output = runServiceApi([
    'request',
    '--env', liveEnv,
    '--service', 'platform-account-api',
    '--path', '/auth/info',
    '--auth', 'admin',
    '--timeout', '10',
    '--raw',
  ]);
  assert.equal(typeof output.status_code, 'number');
  assert.equal(output.request.auth_mode, 'admin');
  assert.equal(output.request.headers.Cookie, '<redacted>');
  assert.equal(String(output.service_resolution.service).toLowerCase(), 'platform-account-api');
  assert.ok(output.service_resolution.instance_count >= 1);
  assert.match(output.request.url, /\/auth\/info$/);
  assert.doesNotMatch(JSON.stringify(output), new RegExp(envAuthState.adminCookie.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('live service-api request --raw redacts admin cookie', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  const envAuthState = getEnvAuthState(readAuthState());
  if (!envConfig.adminAuthCheckUrl) assert.fail(`adminAuthCheckUrl missing for ${liveEnv}`);
  if (!envAuthState.adminCookie) assert.fail(`adminCookie missing; run scripts/service-api auth admin --env ${liveEnv}`);

  const output = runServiceApi([
    'request',
    '--env', liveEnv,
    '--url', envConfig.adminAuthCheckUrl,
    '--auth', 'admin',
    '--timeout', '10',
    '--raw',
  ]);
  assert.equal(output.status_code, 200);
  assert.equal(output.request.auth_mode, 'admin');
  assert.equal(output.request.headers.Cookie, '<redacted>');
  assert.equal(typeof output.response_headers, 'object');
  assert.doesNotMatch(JSON.stringify(output), new RegExp(envAuthState.adminCookie.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('live service-api request --auth customer keeps compact output', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  const envAuthState = getEnvAuthState(readAuthState());
  if (!envConfig.customerAuthCheckUrl) assert.fail(`customerAuthCheckUrl missing for ${liveEnv}`);
  if (!envAuthState.customerCookie) assert.fail(`customerCookie missing; run scripts/service-api auth customer --env ${liveEnv}`);

  const output = runServiceApi([
    'request',
    '--env', liveEnv,
    '--url', envConfig.customerAuthCheckUrl,
    '--auth', 'customer',
    '--timeout', '10',
  ]);
  assertCompactSuccess(output);
});

test('live service-api request resolves customer service path successfully', () => {
  const envAuthState = getEnvAuthState(readAuthState());
  if (!envAuthState.customerCookie) assert.fail(`customerCookie missing; run scripts/service-api auth customer --env ${liveEnv}`);

  const output = runServiceApi([
    'request',
    '--env', liveEnv,
    '--service', 'api-community-web',
    '--path', '/web/users/details',
    '--auth', 'customer',
    '--timeout', '10',
  ]);
  assertCompactSuccess(output);
});

test('live service-api request --auth custom keeps compact output', () => {
  const authState = readAuthState();
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  const preferredOrigin = envConfig.adminAuthCheckUrl ? new URL(envConfig.adminAuthCheckUrl).origin : '';
  const customEntry = Object.values(authState.customCookies || {})
    .find((entry) => entry && entry.cookie && entry.authCheckUrl && (!preferredOrigin || entry.authCheckUrl.startsWith(preferredOrigin)))
    || Object.values(authState.customCookies || {})
      .find((entry) => entry && entry.cookie && entry.authCheckUrl);
  if (!customEntry) {
    assert.fail('custom cookie missing; run scripts/service-api auth custom --login-url URL --auth-check-url URL');
  }

  const output = runServiceApi([
    'request',
    '--url', customEntry.authCheckUrl,
    '--auth', 'custom',
    '--timeout', '10',
  ]);
  assertCompactSuccess(output);
});

test('live service-api request --auth custom stays scoped to final URL origin', () => {
  const config = readConfig();
  const envConfig = getEnvConfig(config);
  if (!envConfig.adminAuthCheckUrl) assert.fail(`adminAuthCheckUrl missing for ${liveEnv}`);
  const origin = new URL(envConfig.adminAuthCheckUrl).origin;
  const authState = readAuthState();
  const customEntry = authState.customCookies && authState.customCookies[origin];
  if (!customEntry || !customEntry.cookie) {
    assert.fail('custom cookie missing; run scripts/service-api auth custom --login-url URL --auth-check-url URL');
  }

  const result = spawnSync(serviceApi, [
    '--config', configFile,
    'request',
    '--env', liveEnv,
    '--service', 'platform-account-api',
    '--path', '/auth/info',
    '--auth', 'custom',
    '--timeout', '10',
  ], {
    cwd: skillRoot,
    encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /custom_cookie_missing/);
  assert.match(result.stderr, /auth custom --login-url/);
  assert.doesNotMatch(result.stderr, new RegExp(customEntry.cookie.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});
