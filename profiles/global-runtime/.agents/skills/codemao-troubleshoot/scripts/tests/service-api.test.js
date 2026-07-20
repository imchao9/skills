const assert = require('node:assert/strict');
const EventEmitter = require('node:events');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const serviceApi = path.join(skillRoot, 'scripts', 'service-api');
const serviceApiModule = require('../service-api');

function runCli(args) {
  const env = { ...process.env };
  const authFile = authFileFromArgs(args);
  if (authFile) env.SERVICE_API_AUTH_FILE = authFile;
  return spawnSync(serviceApi, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    env,
  });
}

function runCliAsync(args) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env };
    const authFile = authFileFromArgs(args);
    if (authFile) env.SERVICE_API_AUTH_FILE = authFile;
    const child = spawn(serviceApi, args, {
      cwd: skillRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      env,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', reject);
    child.on('close', (status) => resolve({ status, stdout, stderr }));
  });
}

function authFileForConfig(configFile) {
  return path.join(path.dirname(configFile), 'service-api-auth.json');
}

function authFileFromArgs(args) {
  const index = args.indexOf('--config');
  if (index === -1 || !args[index + 1]) return '';
  const authFile = authFileForConfig(args[index + 1]);
  return fs.existsSync(authFile) ? authFile : '';
}

function writeConfig(serverUrl) {
  return writeConfigWithUrls({
    eurekaServerUrl: serverUrl,
    apolloDomain: serverUrl,
    apolloPortalUrl: serverUrl,
  });
}

function writeConfigWithUrls({ eurekaServerUrl, apolloDomain, apolloPortalUrl }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'service-api-test-'));
  const configFile = path.join(dir, 'service-api.config.json');
  fs.writeFileSync(configFile, JSON.stringify({
    test: {
      eurekaServerUrl,
      apolloDomain,
      apolloPortalUrl,
      apolloPortalAuth: {
        username: 'apollo',
        password: 'portal-password',
      },
      adminLoginUrl: `${apolloPortalUrl}/login`,
      adminAuthCheckUrl: `${apolloPortalUrl}/auth/info`,
      adminRequiredCookies: [],
      customerLoginUrl: `${apolloPortalUrl}/customer-login`,
      customerAuthCheckUrl: `${apolloPortalUrl}/web/users/details`,
      customerRequiredCookies: [],
    },
    staging: {
      eurekaServerUrl,
      apolloDomain,
      apolloPortalUrl,
      apolloPortalAuth: {
        username: 'apollo',
        password: 'portal-password',
      },
      adminLoginUrl: `${apolloPortalUrl}/login`,
      adminAuthCheckUrl: `${apolloPortalUrl}/auth/info`,
      adminRequiredCookies: [],
      customerLoginUrl: `${apolloPortalUrl}/customer-login`,
      customerAuthCheckUrl: `${apolloPortalUrl}/web/users/details`,
      customerRequiredCookies: [],
    },
    press: {
      eurekaServerUrl,
      apolloDomain,
      apolloPortalUrl,
      apolloPortalAuth: {
        username: 'apollo',
        password: 'portal-password',
      },
      adminLoginUrl: `${apolloPortalUrl}/login`,
      adminAuthCheckUrl: `${apolloPortalUrl}/auth/info`,
      adminRequiredCookies: [],
      customerLoginUrl: `${apolloPortalUrl}/customer-login`,
      customerAuthCheckUrl: `${apolloPortalUrl}/web/users/details`,
      customerRequiredCookies: [],
    },
  }));
  fs.writeFileSync(authFileForConfig(configFile), JSON.stringify({
    test: {
      adminCookie: 'sid=test-admin-cookie',
      customerCookie: 'sid=test-customer-cookie',
    },
    staging: {
      adminCookie: 'sid=staging-admin-cookie',
      customerCookie: 'sid=staging-customer-cookie',
    },
    press: {
      adminCookie: 'sid=press-admin-cookie',
      customerCookie: 'sid=press-customer-cookie',
    },
    customCookies: {},
  }));
  return configFile;
}

async function withServer(handler, fn) {
  const requests = [];
  const server = http.createServer((req, res) => {
    requests.push({
      method: req.method,
      url: req.url,
      headers: req.headers,
    });
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      requests[requests.length - 1].body = body;
      handler(req, res, body);
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    return await fn(`http://127.0.0.1:${port}`, requests);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

function sendJson(res, statusCode, payload, headers = {}) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json', ...headers });
  res.end(JSON.stringify(payload));
}

function sendText(res, statusCode, body, headers = {}) {
  res.writeHead(statusCode, { 'Content-Type': 'text/html', ...headers });
  res.end(body);
}

function eurekaApp(name, instances) {
  return {
    name,
    instance: instances.map((homePageUrl, index) => ({
      status: 'UP',
      homePageUrl,
      healthCheckUrl: `${homePageUrl.replace(/\/+$/, '')}/health`,
      ipAddr: `10.0.0.${index + 1}`,
      port: { $: 8080 },
    })),
  };
}

test('service-api help is available through the public entry point', () => {
  const result = runCli(['--help']);

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /service-api/);
  assert.match(result.stdout, /config/);
  assert.match(result.stdout, /discover/);
  assert.match(result.stdout, /request/);
});

test('service-api subcommand help does not load config or cookie', () => {
  for (const args of [
    ['discover', '--help'],
    ['discover', 'get', '--help'],
    ['discover', 'list', '-h'],
    ['config', '--help'],
    ['config', 'get', '--help'],
    ['config', 'exists', '-h'],
    ['auth', '--help'],
    ['request', '--help'],
  ]) {
    const result = runCli(args);
    assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
    assert.match(result.stdout, /usage:/);
    assert.doesNotMatch(result.stderr, /config_missing|cookie_missing/);
  }
});

test('service-api rejects old top-level Apollo command', () => {
  const result = runCli(['apollo', '--env', 'test', '--app', 'demo']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unknown_command/);
});

test('service-api rejects prod config before loading config', () => {
  const result = runCli(['config', 'get', '--env', 'prod', '--app', 'demo']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_env/);
  assert.match(result.stderr, /prod/);
  assert.doesNotMatch(result.stderr, /env_missing/);
});

test('service-api rejects prod service request before loading config', () => {
  const result = runCli(['request', '--env', 'prod', '--service', 'demo-service', '--path', '/api']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_env/);
  assert.match(result.stderr, /prod/);
  assert.doesNotMatch(result.stderr, /env_missing/);
});

test('service-api request validates related target and env options', () => {
  assert.match(
    runCli(['request', '--url', 'http://example.test/api', '--service', 'demo']).stderr,
    /request_target_invalid/,
  );
  assert.match(
    runCli(['request', '--url', 'http://example.test/api', '--path', '/api']).stderr,
    /--path requires --service/,
  );
  assert.match(
    runCli(['request', '--url', 'http://example.test/api', '--index', '1']).stderr,
    /--index requires --service/,
  );
  assert.match(
    runCli(['request', '--env', 'test', '--url', 'http://example.test/api']).stderr,
    /--env applies only with --service or --auth admin\/customer/,
  );
});

test('service-api rejects removed token auth modes', () => {
  const result = runCli([
    'request',
    '--env', 'test',
    '--url', 'http://example.test/api',
    '--auth', 'internal-auth',
  ]);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /auth_mode_invalid/);
  assert.match(result.stderr, /internal-auth/);
});

test('service-api rejects unsupported options per action', () => {
  const discoverResult = runCli(['discover', 'list', '--service', 'demo']);
  assert.equal(discoverResult.status, 2);
  assert.match(discoverResult.stderr, /unknown_argument: --service/);

  const configResult = runCli(['config', 'get', '--app', 'demo', '--raw']);
  assert.equal(configResult.status, 2);
  assert.match(configResult.stderr, /unknown_argument: --raw/);
});

test('service-api rejects invalid list pagination', () => {
  const missingConfig = path.join(os.tmpdir(), 'missing-service-api-config.json');
  const pageResult = runCli(['--config', missingConfig, 'discover', 'list', '--page', '0']);
  assert.equal(pageResult.status, 2);
  assert.match(pageResult.stderr, /argument_invalid_range: --page/);
  assert.doesNotMatch(pageResult.stderr, /config_missing/);

  const sizeResult = runCli(['--config', missingConfig, 'config', 'list', '--page-size', '101']);
  assert.equal(sizeResult.status, 2);
  assert.match(sizeResult.stderr, /argument_invalid_range: --page-size/);
  assert.doesNotMatch(sizeResult.stderr, /config_missing/);
});

test('service-api auth custom validates arguments before loading config', () => {
  const missingConfig = path.join(os.tmpdir(), 'missing-service-api-config.json');
  const result = runCli(['--config', missingConfig, 'auth', 'custom']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /argument_missing: --login-url/);
  assert.doesNotMatch(result.stderr, /config_missing/);
});

test('service-api auth admin writes cookie into output auth state without returning cookie values', async () => {
  const configFile = writeConfig('http://127.0.0.1:1');
  const authFile = authFileForConfig(configFile);
  const result = await serviceApiModule.writeServiceAuthToFile({
    type: 'admin',
    env: 'test',
    authCheckUrl: 'https://test-internal-account-api.codemao.cn/auth/info',
    requiredCookies: ['authorization'],
  }, authFile, [
    { name: 'authorization', value: 'secret-token', domain: 'test-internal-account-api.codemao.cn' },
    { name: 'other', value: 'codemao-domain-cookie', domain: '.codemao.cn' },
    { name: 'external', value: 'skip', domain: 'example.com' },
  ]);

  assert.equal(result.type, 'admin');
  assert.equal(result.cookie_count, 2);
  assert.deepEqual(result.cookie_names, ['authorization', 'other']);
  assert.doesNotMatch(JSON.stringify(result), /secret-token|codemao-domain-cookie/);
  assert.equal(result.auth_state_path, authFile);
  const config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
  assert.equal(config.test.adminCookie, undefined);
  const authState = JSON.parse(fs.readFileSync(authFile, 'utf8'));
  assert.equal(authState.test.adminCookie, 'authorization=secret-token; other=codemao-domain-cookie');
});

test('service-api auth custom writes cookie by auth-check origin', async () => {
  const configFile = writeConfig('http://127.0.0.1:1');
  const authFile = authFileForConfig(configFile);
  const result = await serviceApiModule.writeServiceAuthToFile({
    type: 'custom',
    loginUrl: 'https://custom.codemao.cn/login',
    authCheckUrl: 'https://custom.codemao.cn/api/me',
    requiredCookies: [],
  }, authFile, [
    { name: 'sid', value: 'custom-session', domain: 'custom.codemao.cn' },
    { name: 'external', value: 'skip', domain: 'example.com' },
  ]);

  assert.equal(result.type, 'custom');
  assert.equal(result.origin, 'https://custom.codemao.cn');
  assert.doesNotMatch(JSON.stringify(result), /custom-session/);
  const config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
  assert.equal(config.customCookies, undefined);
  const authState = JSON.parse(fs.readFileSync(authFile, 'utf8'));
  assert.equal(authState.customCookies['https://custom.codemao.cn'].cookie, 'sid=custom-session');
  assert.equal(authState.customCookies['https://custom.codemao.cn'].authCheckUrl, 'https://custom.codemao.cn/api/me');
});

test('service-api auth only accepts successful auth-check response', () => {
  const args = { authCheckUrl: 'https://admin.codemao.cn/auth/info' };
  const okCheckResponse = {
    ok: () => true,
    url: () => 'https://admin.codemao.cn/auth/info',
  };
  const otherOkResponse = {
    ok: () => true,
    url: () => 'https://admin.codemao.cn/static/app.js',
  };
  const failedCheckResponse = {
    ok: () => false,
    url: () => 'https://admin.codemao.cn/auth/info',
  };

  assert.equal(serviceApiModule.looksLikeServiceAuthSuccess(okCheckResponse, args), true);
  assert.equal(serviceApiModule.looksLikeServiceAuthSuccess(otherOkResponse, args), false);
  assert.equal(serviceApiModule.looksLikeServiceAuthSuccess(failedCheckResponse, args), false);
});

test('service-api config get requires an explicit output filter', async () => {
  await withServer((_req, res) => {
    sendJson(res, 500, { message: 'must not query upstream without filter' });
  }, async (serverUrl, requests) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'get',
      '--env', 'test',
      '--app', 'demo',
      '--namespace', 'application',
    ]);

    assert.equal(result.status, 2);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /config_filter_required/);
    assert.equal(requests.length, 0);
  });
});

test('service-api config get supports keys, key, prefix, keyword, and all output modes', async () => {
  await withServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(url.pathname, '/configs/demo/default/application');
    assert.equal(url.searchParams.get('ip'), '10.240.7.233');
    sendJson(res, 200, {
      namespaceName: 'application',
      configurations: {
        'spring.datasource.url': 'jdbc:mysql://db:3306/demo',
        'spring.datasource.password': 'db-secret',
        'spring.redis.host': 'redis-host',
        'feature.enabled': 'true',
      },
    });
  }, async (serverUrl) => {
    const configPath = writeConfig(serverUrl);
    const base = ['--config', configPath, 'config', 'get', '--env', 'test', '--app', 'demo', '--namespace', 'application'];

    const keysResult = await runCliAsync([...base, '--keys']);
    assert.equal(keysResult.status, 0, keysResult.stderr);
    assert.deepEqual(JSON.parse(keysResult.stdout), {
      application: [
        'feature.enabled',
        'spring.datasource.password',
        'spring.datasource.url',
        'spring.redis.host',
      ],
    });

    const keyResult = await runCliAsync([...base, '--key', 'spring.datasource.url']);
    assert.equal(keyResult.status, 0, keyResult.stderr);
    assert.deepEqual(JSON.parse(keyResult.stdout), {
      application: {
        'spring.datasource.url': 'jdbc:mysql://db:3306/demo',
      },
    });

    const prefixResult = await runCliAsync([...base, '--prefix', 'spring.datasource']);
    assert.equal(prefixResult.status, 0, prefixResult.stderr);
    const prefixOutput = JSON.parse(prefixResult.stdout);
    assert.deepEqual(Object.keys(prefixOutput.application).sort(), [
      'spring.datasource.password',
      'spring.datasource.url',
    ]);
    assert.match(prefixOutput.application['spring.datasource.password'], /^sealed:v1:/);

    const keywordResult = await runCliAsync([...base, '--keyword', 'redis']);
    assert.equal(keywordResult.status, 0, keywordResult.stderr);
    assert.deepEqual(JSON.parse(keywordResult.stdout), {
      application: {
        'spring.redis.host': 'redis-host',
      },
    });

    const allResult = await runCliAsync([...base, '--all']);
    assert.equal(allResult.status, 0, allResult.stderr);
    assert.deepEqual(Object.keys(JSON.parse(allResult.stdout).application).sort(), [
      'feature.enabled',
      'spring.datasource.password',
      'spring.datasource.url',
      'spring.redis.host',
    ]);
  });
});

test('service-api config get queries default Apollo namespaces when output mode is explicit', async () => {
  await withServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(url.pathname.startsWith('/configs/demo/default/'), true);
    assert.equal(url.searchParams.get('ip'), '10.240.7.233');
    sendJson(res, 200, {
      namespaceName: decodeURIComponent(url.pathname.split('/').pop()),
      configurations: { feature: 'on' },
    });
  }, async (serverUrl, requests) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'get',
      '--env', 'test',
      '--app', 'demo',
      '--all',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.deepEqual(Object.keys(output), ['application', 'application-volatile']);
    assert.deepEqual(output.application, { feature: 'on' });
    assert.deepEqual(output['application-volatile'], { feature: 'on' });
    assert.equal(output.env, undefined);
    assert.equal(output.app, undefined);
    assert.equal(output.ip, undefined);
    assert.equal(output.results, undefined);
    assert.equal(requests.length, 2);
  });
});

test('service-api config get prints compact config map and seals password fields', async () => {
  await withServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(url.pathname, '/configs/demo/default/application');
    sendJson(res, 200, {
      appId: 'demo',
      cluster: 'default',
      namespaceName: 'application',
      releaseKey: 'release-1',
      configurations: {
        apollo_hover_content: 'ignore-me',
        'spring.datasource.password': 'db-secret',
        'redis.password': 'redis-secret',
        'spring.data.mongodb.uri': 'mongodb://test_all:mongo-secret@mongo-a:3717,mongo-b:3717/demo?authSource=admin',
        normalKey: 'visible-value',
        nested: {
          apollo_hover_content: 'ignore-nested',
          password: 'nested-secret',
          token: 'token-stays-visible',
        },
      },
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'get',
      '--env', 'test',
      '--app', 'demo',
      '--namespace', 'application',
      '--all',
    ]);

    assert.equal(result.status, 0, result.stderr);
    assert.doesNotMatch(result.stdout, /db-secret|redis-secret|mongo-secret|nested-secret/);
    assert.match(result.stdout, /token-stays-visible/);

    const output = JSON.parse(result.stdout);
    assert.deepEqual(Object.keys(output), ['application']);
    assert.equal(result.stdout.includes('headers'), false);
    assert.equal(result.stdout.includes('status_code'), false);
    assert.equal(result.stdout.includes('namespaceName'), false);
    assert.equal(result.stdout.includes('releaseKey'), false);
    assert.equal(result.stdout.includes('apollo_hover_content'), false);

    const configs = output.application;
    assert.equal(configs.normalKey, 'visible-value');
    assert.equal(configs.nested.token, 'token-stays-visible');
    for (const sealed of [
      configs['spring.datasource.password'],
      configs['redis.password'],
      configs.nested.password,
    ]) {
      assert.match(sealed, /^sealed:v1:/);
      assert.equal(serviceApiModule.isSealedCredential(sealed), true);
      assert.equal(serviceApiModule.unsealCredential(sealed).endsWith('-secret'), true);
    }

    const mongoUri = configs['spring.data.mongodb.uri'];
    assert.match(mongoUri, /^mongodb:\/\/test_all:sealed%3Av1%3A/);
    const encodedPassword = mongoUri.match(/^mongodb:\/\/[^:]+:([^@]+)@/)[1];
    const sealedPassword = decodeURIComponent(encodedPassword);
    assert.equal(serviceApiModule.isSealedCredential(sealedPassword), true);
    assert.equal(serviceApiModule.unsealCredential(sealedPassword), 'mongo-secret');
  });
});

test('service-api config get fails compactly when Apollo namespace fails', async () => {
  await withServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    if (url.pathname.endsWith('/application')) {
      sendJson(res, 200, {
        namespaceName: 'application',
        configurations: { feature: 'on' },
      });
      return;
    }
    sendJson(res, 404, {
      message: 'very noisy upstream body',
      headers: { should: 'not appear' },
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'get',
      '--env', 'test',
      '--app', 'demo',
      '--all',
    ]);

    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /\[apollo_config_failed\]/);
    assert.match(result.stderr, /namespace=application-volatile/);
    assert.match(result.stderr, /status=404/);
    assert.doesNotMatch(result.stderr, /very noisy|headers|feature/);
  });
});

test('service-api discover get resolves selected Eureka instance with compact output', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', [
        'http://10.0.0.1:8080/',
        'http://10.0.0.2:8080/',
      ]),
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'get',
      '--env', 'test',
      '--service', 'DEMO-SERVICE',
      '--index', '1',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.env, undefined);
    assert.equal(output.service, undefined);
    assert.equal(output.instance_count, 2);
    assert.equal(output.index, 1);
    assert.equal(output.status, 'UP');
    assert.equal(output.url, 'http://10.0.0.2:8080/');
    assert.equal(output.health_url, 'http://10.0.0.2:8080/health');
    assert.equal(output.selected_index, undefined);
    assert.equal(output.selected_home_url, undefined);
    assert.equal(output.selected_health_url, undefined);
    assert.equal(output.selected_instance, undefined);
    assert.equal(output.instances, undefined);
    assert.equal(output.raw, undefined);
  });
});

test('service-api discover get treats service names as case-insensitive', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', ['http://10.0.0.1:8080/']),
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'get',
      '--env', 'test',
      '--service', 'demo-service',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.service, undefined);
    assert.equal(output.url, 'http://10.0.0.1:8080/');
  });
});

test('service-api discover get --raw includes raw Eureka response', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', ['http://10.0.0.1:8080/']),
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'get',
      '--env', 'test',
      '--service', 'DEMO-SERVICE',
      '--raw',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.url, 'http://10.0.0.1:8080/');
    assert.equal(Array.isArray(output.instances), true);
    assert.equal(output.instances[0].ip_addr, '10.0.0.1');
    assert.equal(output.raw.application.name, 'DEMO-SERVICE');
  });
});

test('service-api discover list prints service names and representative URLs only', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps');
    sendJson(res, 200, {
      applications: {
        application: [
          eurekaApp('B-SERVICE', ['http://10.0.0.2:8080/']),
          eurekaApp('A-SERVICE', ['http://10.0.0.1:8080/', 'http://10.0.0.3:8080/']),
          eurekaApp('C-SERVICE', ['http://10.0.0.4:8080/']),
        ],
      },
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'list',
      '--env', 'test',
      '--keyword', 'service',
      '--page-size', '2',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.total, 3);
    assert.equal(output.total_count, undefined);
    assert.equal(output.returned_count, undefined);
    assert.equal(output.page_count, undefined);
    assert.equal(output.env, undefined);
    assert.equal(output.page, 1);
    assert.equal(output.page_size, 2);
    assert.equal(output.next_page, 2);
    assert.deepEqual(output.services.map((item) => item.service), ['A-SERVICE', 'B-SERVICE']);
    assert.deepEqual(output.services[0], {
      service: 'A-SERVICE',
      instance_count: 2,
      url: 'http://10.0.0.1:8080/',
      status: 'UP',
    });
    assert.equal(output.services[0].instance, undefined);
  });
});

test('service-api discover exists uses Eureka app lookup', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', ['http://10.0.0.1:8080/']),
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'exists',
      '--env', 'test',
      '--service', 'DEMO-SERVICE',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.exists, true);
    assert.equal(output.instance_count, 1);
    assert.equal(output.url, 'http://10.0.0.1:8080/');
    assert.equal(output.env, undefined);
    assert.equal(output.service, undefined);
    assert.equal(output.status_code, undefined);
  });
});

test('service-api discover exists returns false on Eureka 404', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/MISSING-SERVICE');
    sendJson(res, 404, { message: 'not found' });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'discover',
      'exists',
      '--env', 'test',
      '--service', 'MISSING-SERVICE',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.exists, false);
    assert.equal(output.status_code, undefined);
  });
});

test('service-api converts URL credentials to basic auth header', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    assert.equal(req.headers.authorization, `Basic ${Buffer.from('discovery:secret').toString('base64')}`);
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', ['http://10.0.0.1:8080/']),
    });
  }, async (serverUrl) => {
    const url = new URL(serverUrl);
    url.username = 'discovery';
    url.password = 'secret';
    const result = await runCliAsync([
      '--config', writeConfigWithUrls({ eurekaServerUrl: url.toString(), apolloDomain: serverUrl, apolloPortalUrl: serverUrl }),
      'discover',
      'get',
      '--env', 'test',
      '--service', 'DEMO-SERVICE',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.url, 'http://10.0.0.1:8080/');
  });
});

test('service-api config list logs in to Apollo Portal and prints compact apps', async () => {
  await withServer((req, res, body) => {
    if (req.method === 'POST' && req.url === '/signin') {
      assert.equal(req.headers['content-type'], 'application/x-www-form-urlencoded');
      assert.match(body, /username=apollo/);
      assert.match(body, /password=portal-password/);
      res.writeHead(302, { 'Set-Cookie': 'JSESSIONID=test-session; Path=/; HttpOnly' });
      res.end();
      return;
    }
    if (req.method === 'GET' && req.url === '/apps?appIds=') {
      assert.equal(req.headers.cookie, 'JSESSIONID=test-session');
      sendJson(res, 200, {
        content: [
          { appId: 'demo-api', name: 'Demo API', orgName: 'backend', ownerName: 'dev-a', extra: 'omit' },
          { appId: 'other-api', name: 'Other API', orgName: 'backend', ownerName: 'dev-b', extra: 'omit' },
        ],
      });
      return;
    }
    sendJson(res, 404, { message: 'unexpected' });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'list',
      '--env', 'test',
      '--keyword', 'demo',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.total, 1);
    assert.equal(output.total_count, undefined);
    assert.equal(output.returned_count, undefined);
    assert.equal(output.page_count, undefined);
    assert.equal(output.env, undefined);
    assert.equal(output.page, 1);
    assert.equal(output.next_page, null);
    assert.deepEqual(output.apps[0], {
      app_id: 'demo-api',
      name: 'Demo API',
      org_name: 'backend',
      owner_name: 'dev-a',
    });
    assert.doesNotMatch(result.stdout, /portal-password|JSESSIONID/);
  });
});

test('service-api config list reports Apollo Portal login failure without leaking password', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/signin');
    sendText(res, 401, '<html>login failed</html>');
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'list',
      '--env', 'test',
    ]);

    assert.equal(result.status, 1);
    assert.match(result.stderr, /apollo_portal_login_failed/);
    assert.doesNotMatch(result.stderr, /portal-password/);
  });
});

test('service-api config list rejects non-JSON Portal apps response', async () => {
  await withServer((req, res) => {
    if (req.method === 'POST' && req.url === '/signin') {
      res.writeHead(302, { 'Set-Cookie': 'JSESSIONID=test-session; Path=/; HttpOnly' });
      res.end();
      return;
    }
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/apps?appIds=');
    sendText(res, 200, '<html><form action="/signin">login</form></html>');
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'list',
      '--env', 'test',
    ]);

    assert.equal(result.status, 1);
    assert.match(result.stderr, /apollo_portal_auth_invalid/);
    assert.doesNotMatch(result.stderr, /JSESSIONID|portal-password/);
  });
});

test('service-api config exists checks Apollo internal config endpoint', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(url.pathname, '/configs/demo-api/default/application');
    assert.equal(url.searchParams.get('ip'), '10.240.7.233');
    sendJson(res, 200, {
      appId: 'demo-api',
      namespaceName: 'application',
      configurations: {},
    });
  }, async (serverUrl, requests) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'exists',
      '--env', 'test',
      '--app', 'demo-api',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.exists, true);
    assert.equal(output.namespace, 'application');
    assert.equal(output.status_code, 200);
    assert.equal(output.ip, undefined);
    assert.equal(requests.length, 1);
    assert.notEqual(requests[0].url, '/signin');
  });
});

test('service-api config exists returns false on Apollo 404', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.match(req.url, /^\/configs\/missing-api\/default\/application\?/);
    sendJson(res, 404, { message: 'not found' });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'config',
      'exists',
      '--env', 'test',
      '--app', 'missing-api',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.exists, false);
    assert.equal(output.status_code, 404);
  });
});

test('service-api request sends configured admin cookie and prints response evidence', async () => {
  await withServer((req, res, body) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(req.method, 'POST');
    assert.equal(url.pathname, '/api/check');
    assert.equal(url.searchParams.get('trace'), '1');
    assert.equal(req.headers.cookie, 'sid=test-admin-cookie');
    assert.equal(req.headers['x-debug'], 'yes');
    assert.deepEqual(JSON.parse(body), { id: 123 });
    sendJson(res, 200, { ok: true });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'request',
      '--env', 'test',
      '--url', `${serverUrl}/api/check`,
      '--method', 'POST',
      '--auth', 'admin',
      '--query', 'trace=1',
      '--header', 'X-Debug: yes',
      '--json-body', '{"id":123}',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.status_code, 200);
    assert.deepEqual(output.body, { ok: true });
    assert.equal(output.env, undefined);
    assert.equal(output.request, undefined);
    assert.equal(output.service_resolution, undefined);
    assert.equal(output.response_headers, undefined);
  });
});

test('service-api request --raw prints diagnostics without exposing cookies', async () => {
  await withServer((req, res, body) => {
    assert.equal(req.headers.cookie, 'sid=test-admin-cookie');
    assert.deepEqual(JSON.parse(body), { id: 123 });
    sendJson(res, 200, { ok: true });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'request',
      '--env', 'test',
      '--url', `${serverUrl}/api/check`,
      '--method', 'POST',
      '--auth', 'admin',
      '--json-body', '{"id":123}',
      '--raw',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.status_code, 200);
    assert.deepEqual(output.body, { ok: true });
    assert.equal(output.request.method, 'POST');
    assert.equal(output.request.auth_mode, 'admin');
    assert.equal(output.request.headers.Cookie, '<redacted>');
    assert.deepEqual(output.request.json_body, { id: 123 });
    assert.ok(output.response_headers);
  });
});

test('service-api request sends custom cookie by request origin', async () => {
  await withServer((req, res) => {
    assert.equal(req.headers.cookie, 'sid=custom-cookie');
    sendJson(res, 200, { ok: true });
  }, async (serverUrl) => {
    const configFile = writeConfig(serverUrl);
    const authFile = authFileForConfig(configFile);
    const authState = JSON.parse(fs.readFileSync(authFile, 'utf8'));
    authState.customCookies[new URL(serverUrl).origin] = {
      authCheckUrl: `${serverUrl}/api/me`,
      requiredCookies: [],
      cookie: 'sid=custom-cookie',
    };
    fs.writeFileSync(authFile, JSON.stringify(authState));
    const result = await runCliAsync([
      '--config', configFile,
      'request',
      '--url', `${serverUrl}/api/check`,
      '--auth', 'custom',
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.status_code, 200);
    assert.deepEqual(output.body, { ok: true });
    assert.equal(output.request, undefined);
  });
});

test('service-api request explicit URL with no auth does not require env or config', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/api/public');
    sendJson(res, 200, { public: true });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', path.join(os.tmpdir(), 'service-api-missing-config.json'),
      'request',
      '--url', `${serverUrl}/api/public`,
    ]);

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.deepEqual(Object.keys(output).sort(), ['body', 'status_code']);
    assert.equal(output.status_code, 200);
    assert.deepEqual(output.body, { public: true });
  });
});

test('service-api request resolves service through Eureka before calling path', async () => {
  let serviceBaseUrl = '';
  await withServer((req, res) => {
    if (req.url === '/eureka/apps/DEMO-SERVICE') {
      return sendJson(res, 200, {
        application: eurekaApp('DEMO-SERVICE', [`${serviceBaseUrl}/`]),
      });
    }
    if (req.url === '/api/health?trace=1') {
      assert.equal(req.method, 'GET');
      return sendJson(res, 200, { healthy: true });
    }
    return sendJson(res, 404, { error: 'unexpected path' });
  }, async (serverUrl, requests) => {
    serviceBaseUrl = serverUrl;
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'request',
      '--env', 'test',
      '--service', 'demo-service',
      '--path', '/api/health',
      '--query', 'trace=1',
    ]);

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(requests.map((request) => request.url), [
      '/eureka/apps/DEMO-SERVICE',
      '/api/health?trace=1',
    ]);
    const output = JSON.parse(result.stdout);
    assert.deepEqual(Object.keys(output).sort(), ['body', 'status_code']);
    assert.equal(output.status_code, 200);
    assert.deepEqual(output.body, { healthy: true });
  });
});

test('service-api request --auth custom guides cookie capture after service resolution', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/eureka/apps/DEMO-SERVICE');
    sendJson(res, 200, {
      application: eurekaApp('DEMO-SERVICE', ['http://api.example.test/']),
    });
  }, async (serverUrl) => {
    const result = await runCliAsync([
      '--config', writeConfig(serverUrl),
      'request',
      '--env', 'test',
      '--service', 'DEMO-SERVICE',
      '--path', '/api/me',
      '--auth', 'custom',
    ]);

    assert.equal(result.status, 1);
    assert.match(result.stderr, /custom_cookie_missing/);
    assert.match(result.stderr, /http:\/\/api\.example\.test/);
    assert.match(result.stderr, /service-api auth custom --login-url <login-url> --auth-check-url/);
  });
});

test('service-api browser auth lifecycle exits when the login tab is closed', () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const browser = new EventEmitter();
  context.pages = () => [page];
  context.browser = () => browser;
  const calls = [];

  const lifecycle = serviceApiModule.installBrowserAuthCloseHandlers(context, (error) => {
    calls.push(error);
  });
  if (lifecycle.getPageCount() === 0) lifecycle.markPage(page);

  page.emit('close');

  assert.equal(calls.length, 1);
  assert.match(calls[0].message, /登录已取消或浏览器已关闭/);
});

test('service-api rejects prod Eureka discovery before loading config', () => {
  const result = runCli(['discover', 'get', '--env', 'prod', '--service', 'demo-service']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_env/);
  assert.match(result.stderr, /prod/);
  assert.doesNotMatch(result.stderr, /env_missing/);
});
