const assert = require('node:assert/strict');
const EventEmitter = require('node:events');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const dbopsQuery = path.join(skillRoot, 'scripts', 'dbops-query');
const dbopsModule = require('../dbops-query');

function runCli(args, env = {}, input = undefined) {
  return spawnSync(dbopsQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    env: { ...process.env, ...env },
    input,
  });
}

function runCliAsync(args, env = {}, input = '') {
  return new Promise((resolve, reject) => {
    const child = spawn(dbopsQuery, args, {
      cwd: skillRoot,
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
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
    child.stdin.end(input);
  });
}

function writeFixtureFiles(serverUrl, defaults = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbops-query-test-'));
  const configFile = path.join(dir, 'dbops-query.config.json');
  const cookieFile = path.join(dir, 'dbops-auth-cookie.txt');
  fs.writeFileSync(configFile, JSON.stringify({
    defaults: {
      instanceName: '',
      dbName: '',
      schemaName: '',
      tableName: '',
      limitNum: 100,
      ...defaults,
    },
  }));
  fs.writeFileSync(cookieFile, [
    '# dbops auth cookie file',
    '# last non-comment line is used',
    'sessionid=test-session; csrftoken=test-csrf',
    '',
  ].join('\n'));
  return { dir, configFile, cookieFile };
}

function poisonedRuntimeEnv() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbops-query-poison-'));
  const configFile = path.join(dir, 'bad-config.json');
  fs.writeFileSync(configFile, '{bad json');
  return {
    DBOPS_CONFIG_FILE: configFile,
    DBOPS_COOKIE_FILE: path.join(dir, 'missing-cookie.txt'),
    DBOPS_COOKIE: '',
    DBOPS_CSRFTOKEN: '',
    DBOPS_INSTANCE_NAME: '',
    DBOPS_DB_NAME: '',
  };
}

function fixtureEnv(serverUrl, configFile, cookieFile) {
  return {
    NODE_ENV: 'test',
    CODEMAO_DBOPS_QUERY_TEST_BASE_URL: serverUrl,
    DBOPS_CONFIG_FILE: configFile,
    DBOPS_COOKIE_FILE: cookieFile,
  };
}

async function withServer(handler, fn) {
  const requests = [];
  const server = http.createServer((req, res) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      const request = {
        method: req.method,
        url: req.url,
        headers: req.headers,
        body,
      };
      requests.push(request);
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

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(payload));
}

function parseForm(body) {
  return Object.fromEntries(new URLSearchParams(body));
}

test('dbops-query prints usage without authentication when no args are provided', () => {
  const result = runCli([]);

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Usage:/);
  assert.match(result.stderr, /query-on/);
  assert.doesNotMatch(result.stderr, /cookie_missing/);
});

test('dbops-query help does not require authentication', () => {
  const result = runCli(['--help']);

  assert.equal(result.status, 0);
  assert.match(result.stdout, /Usage:/);
  assert.match(result.stdout, /query-on/);
  assert.match(result.stdout, /dbops-query <command> --help/);
  assert.match(result.stdout, /api\s+call dbops platform API fallback/);
  assert.doesNotMatch(result.stdout, /api POST \/query\/favorite\/ query_log_id=123|DBOPS_COOKIE|DBOPS_CSRFTOKEN/);
  assert.doesNotMatch(result.stdout, /--base-url|--login-url|--cookie-file|--storage-state|DBOPS_BASE_URL|DBOPS_SQLQUERY_REFERER/);
  assert.doesNotMatch(result.stderr, /cookie_missing/);
});

test('dbops-query subcommand help is specific and does not require authentication', () => {
  const cases = [
    [['auth', '--help'], /dbops-query auth \[--login-timeout SECONDS\]/, /Does not print cookie values/],
    [['query-on', '--help'], /dbops-query query-on "实例名" "库名"/, /Only SELECT, SHOW, DESC, DESCRIBE, and EXPLAIN are allowed/],
    [['instances', '--help'], /dbops-query instances \[tag_code\]/, /Default tag_code is can_read/],
    [['resources', '--help'], /dbops-query resources "实例名" table db_name=库名/, /List databases, tables, or schemas/],
    [['querylog', '--help'], /dbops-query querylog \[limit=N\] \[offset=N\]/, /recent query logs/],
    [['queryloginfo', '--help'], /dbops-query queryloginfo <log_id>/, /query log detail/],
    [['favorites', '--help'], /dbops-query favorites/, /favorite queries/],
    [['favorite-list', '--help'], /Alias of dbops-query favorites/, /dbops-query favorite-list/],
    [['favorite-find', '--help'], /dbops-query favorite-find <keyword>/, /Search saved favorite/],
    [['favorite-info', '--help'], /dbops-query favorite-info <alias>/, /without running SQL/],
    [['favorite-run', '--help'], /dbops-query favorite-run <alias>/, /Confirm the target instance/],
    [['favorite-query', '--help'], /dbops-query favorite-query <alias>/, /Only readonly SQL is allowed/],
    [['favorite', '--help'], /dbops-query favorite <query_log_id> <alias>/, /changes favorite state/],
    [['unfavorite', '--help'], /dbops-query unfavorite <query_log_id>/, /changes favorite state/],
    [['api', '--help'], /dbops-query api GET \/path/, /POST may change state/],
  ];

  for (const [args, usagePattern, detailPattern] of cases) {
    const result = runCli(args);
    assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
    assert.match(result.stdout, usagePattern, args.join(' '));
    assert.match(result.stdout, detailPattern, args.join(' '));
    assert.doesNotMatch(result.stderr, /cookie_missing|query_target_missing/, args.join(' '));
  }
});

test('dbops-query help does not touch config or cookie state', () => {
  const env = poisonedRuntimeEnv();

  for (const args of [['--help'], ['instances', '--help'], ['api', '--help']]) {
    const result = runCli(args, env);
    assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
    assert.match(result.stdout, /Usage:/);
    assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing|query_target_missing/);
  }
});

test('dbops-query rejects unknown option before loading default query target', () => {
  const result = runCli(['--bad']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\] non-retryable: unknown argument: --bad/);
  assert.doesNotMatch(result.stderr, /query_target_missing|cookie_missing/);
});

test('dbops-query rejects unknown command before loading config or cookie', () => {
  const result = runCli(['badcmd'], poisonedRuntimeEnv());

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\] non-retryable: unknown command: badcmd/);
  assert.doesNotMatch(result.stderr, /readonly_only|config_invalid_json|cookie_missing|query_target_missing/);
});

test('dbops-query rejects subcommand options before loading config or cookie', () => {
  const env = poisonedRuntimeEnv();

  for (const args of [
    ['instances', '--bad'],
    ['resources', 'prod-main', 'table', '--bad'],
    ['querylog', '--bad'],
    ['queryloginfo', '123', '--bad'],
    ['favorites', '--bad'],
    ['favorite-find', 'alias', '--bad'],
    ['favorite-info', 'alias', '--bad'],
    ['favorite-run', 'alias', '--bad'],
    ['favorite', '123', 'alias', '--bad'],
    ['unfavorite', '123', '--bad'],
    ['api', 'GET', '/query/querylog/', '--bad'],
  ]) {
    const result = runCli(args, env);
    assert.equal(result.status, 2, `${args.join(' ')}\n${result.stderr}`);
    assert.match(result.stderr, /\[invalid_argument\]/, args.join(' '));
    assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing|query_target_missing/, args.join(' '));
  }
});

test('dbops-query auth rejects URL and output path override arguments', () => {
  for (const arg of ['--base-url', '--login-url', '--cookie-file', '--storage-state']) {
    const result = runCli(['auth', arg, 'value']);
    assert.equal(result.status, 2, `${arg}\n${result.stderr}`);
    assert.match(result.stderr, /invalid_argument/);
    assert.match(result.stderr, new RegExp(arg));
  }
});

test('dbops-query auth uses built-in login and auth-check URLs outside fake-server tests', () => {
  const previousNodeEnv = process.env.NODE_ENV;
  const previousBaseUrl = process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL;
  delete process.env.NODE_ENV;
  delete process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL;
  try {
    assert.equal(
      dbopsModule.dbopsLoginPageUrl(),
      'https://dbops.codemao.cn/sqlquery/',
    );
    assert.equal(
      dbopsModule.dbopsAuthCheckUrl(),
      'https://dbops.codemao.cn/group/user_all_instances/?tag_codes%5B%5D=can_read',
    );
  } finally {
    if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousNodeEnv;
    if (previousBaseUrl === undefined) delete process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL;
    else process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL = previousBaseUrl;
  }
});

test('dbops-query auth uses fake server URLs only under test override', () => {
  const previousNodeEnv = process.env.NODE_ENV;
  const previousBaseUrl = process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL;
  process.env.NODE_ENV = 'test';
  process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL = 'http://127.0.0.1:12345/';
  try {
    assert.equal(dbopsModule.dbopsLoginPageUrl(), 'http://127.0.0.1:12345/sqlquery/');
    assert.equal(
      dbopsModule.dbopsAuthCheckUrl(),
      'http://127.0.0.1:12345/group/user_all_instances/?tag_codes%5B%5D=can_read',
    );
  } finally {
    if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousNodeEnv;
    if (previousBaseUrl === undefined) delete process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL;
    else process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL = previousBaseUrl;
  }
});

test('dbops-query auth nudges dashboard document responses back to sqlquery', () => {
  const args = {
    baseUrl: 'https://dbops.codemao.cn',
    authCheckUrl: 'https://dbops.codemao.cn/group/user_all_instances/?tag_codes%5B%5D=can_read',
  };
  const response = {
    ok: () => true,
    url: () => 'https://dbops.codemao.cn/dashboard/',
    request: () => ({ resourceType: () => 'document' }),
  };

  assert.equal(dbopsModule.shouldNavigateToSqlquery(response, args), true);
});

test('dbops-query auth does not nudge sqlquery, auth-check, or static responses', () => {
  const args = {
    baseUrl: 'https://dbops.codemao.cn',
    authCheckUrl: 'https://dbops.codemao.cn/group/user_all_instances/?tag_codes%5B%5D=can_read',
  };
  const buildResponse = (url, resourceType = 'document') => ({
    ok: () => true,
    url: () => url,
    request: () => ({ resourceType: () => resourceType }),
  });

  assert.equal(dbopsModule.shouldNavigateToSqlquery(buildResponse('https://dbops.codemao.cn/sqlquery/'), args), false);
  assert.equal(dbopsModule.shouldNavigateToSqlquery(buildResponse(args.authCheckUrl, 'xhr'), args), false);
  assert.equal(dbopsModule.shouldNavigateToSqlquery(buildResponse('https://dbops.codemao.cn/static/app.js', 'script'), args), false);
  assert.equal(dbopsModule.shouldNavigateToSqlquery(buildResponse('https://example.com/dashboard/'), args), false);
});

test('dbops-query auth output path is compact inside skill root', () => {
  assert.equal(
    dbopsModule.dbopsAuthOutputPath(path.join(skillRoot, 'output', 'dbops-auth-cookie.txt')),
    'output/dbops-auth-cookie.txt',
  );
});

test('dbops-query rejects direct non-read-only SQL before authentication', () => {
  const result = runCli(['DELETE FROM tbl_xxx']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
  assert.doesNotMatch(result.stderr, /cookie_missing/);
});

test('dbops-query instances uses config, cookie file, and dbops headers', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/group/user_all_instances/?tag_codes%5B%5D=can_read');
    assert.equal(req.headers.cookie, 'sessionid=test-session; csrftoken=test-csrf');
    assert.equal(req.headers['x-csrftoken'], 'test-csrf');
    assert.equal(req.headers['x-requested-with'], 'XMLHttpRequest');
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'prod-main', db_type: 'mysql', type: 'master' },
      ],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['instances'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    assert.equal(requests.length, 1);
    const output = JSON.parse(result.stdout);
    assert.equal(output.http_status, undefined);
    assert.equal(output.payload, undefined);
    assert.equal(output.count, 1);
    assert.deepEqual(output.items[0], {
      instance_name: 'prod-main',
      db_type: 'mysql',
      type: 'master',
    });
  });
});

test('dbops-query query-on posts readonly SQL and prints rows', async () => {
  await withServer((req, res, body) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      assert.equal(req.method, 'GET');
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
      });
      return;
    }
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/');
    const form = parseForm(body);
    assert.equal(form.instance_name, 'prod-main');
    assert.equal(form.db_name, 'app_db');
    assert.equal(form.sql_content, 'SELECT id, name FROM tbl_demo');
    sendJson(res, 200, {
      status: 0,
      data: {
        column_list: ['id', 'name'],
        rows: [[1, 'alice'], [2, null]],
      },
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['query-on', 'prod-main', 'app_db', 'SELECT id, name FROM tbl_demo'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'id\tname\n1\talice\n2\tNULL\n');
  });
});

test('dbops-query default target posts direct readonly SQL and keeps the first token', async () => {
  await withServer((req, res, body) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
      });
      return;
    }
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/');
    const form = parseForm(body);
    assert.equal(form.instance_name, 'prod-main');
    assert.equal(form.db_name, 'app_db');
    assert.equal(form.sql_content, 'SELECT id FROM tbl_demo');
    sendJson(res, 200, {
      status: 0,
      data: {
        column_list: ['id'],
        rows: [[1]],
      },
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl, {
      instanceName: 'prod-main',
      dbName: 'app_db',
    });
    const result = await runCliAsync(['SELECT id FROM tbl_demo'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'id\n1\n');
  });
});

test('dbops-query default target reads readonly SQL from stdin', async () => {
  await withServer((req, res, body) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
      });
      return;
    }
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/');
    const form = parseForm(body);
    assert.equal(form.instance_name, 'prod-main');
    assert.equal(form.db_name, 'app_db');
    assert.equal(form.sql_content, 'SELECT name FROM tbl_demo');
    sendJson(res, 200, {
      status: 0,
      data: {
        column_list: ['name'],
        rows: [['alice']],
      },
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl, {
      instanceName: 'prod-main',
      dbName: 'app_db',
    });
    const result = await runCliAsync([], fixtureEnv(serverUrl, configFile, cookieFile), 'SELECT name FROM tbl_demo\n');

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'name\nalice\n');
  });
});

test('dbops-query query output redacts mobile numbers and secret columns', async () => {
  await withServer((req, res, body) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
      });
      return;
    }
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/');
    assert.equal(parseForm(body).sql_content, 'SELECT id, mobile, token, note FROM tbl_demo');
    sendJson(res, 200, {
      status: 0,
      data: {
        column_list: ['id', 'mobile', 'token', 'note'],
        rows: [[1, '13812345678', 'secret-token', 'password=plain-secret phone=13900001111']],
      },
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['query-on', 'prod-main', 'app_db', 'SELECT id, mobile, token, note FROM tbl_demo'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /138\*\*\*\*5678/);
    assert.match(result.stdout, /139\*\*\*\*1111/);
    assert.match(result.stdout, /<redacted>/);
    assert.doesNotMatch(result.stdout, /13812345678|13900001111|secret-token|plain-secret/);
  });
});

test('dbops-query resources sends resource lookup parameters', async () => {
  await withServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    assert.equal(url.pathname, '/instance/instance_resource/');
    assert.equal(url.searchParams.get('instance_name'), 'prod-main');
    assert.equal(url.searchParams.get('resource_type'), 'table');
    assert.equal(url.searchParams.get('db_name'), 'app_db');
    sendJson(res, 200, { status: 0, data: ['tbl_demo'] });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['resources', 'prod-main', 'table', 'db_name=app_db'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.http_status, undefined);
    assert.equal(output.payload, undefined);
    assert.equal(output.count, 1);
    assert.deepEqual(output.items, ['tbl_demo']);
  });
});

test('dbops-query queryloginfo posts log id as form data', async () => {
  await withServer((req, res, body) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/queryloginfo/');
    assert.deepEqual(parseForm(body), { log_id: '1053686' });
    sendJson(res, 200, {
      status: 0,
      data: [{
        id: 1053686,
        instance_name: 'prod-main',
        db_name: 'app_db',
        sqllog: 'SELECT * FROM tbl_demo WHERE id = 1',
        create_time: '2026-06-12 10:00:00',
        user_display: 'dev-a',
        noisy: 'omit',
      }],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['queryloginfo', '1053686'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.http_status, undefined);
    assert.equal(output.payload, undefined);
    assert.equal(output.count, 1);
    assert.deepEqual(output.items[0], {
      id: 1053686,
      instance_name: 'prod-main',
      db_name: 'app_db',
      sql: 'SELECT * FROM tbl_demo WHERE id = 1',
      created_at: '2026-06-12 10:00:00',
      user_display: 'dev-a',
    });
  });
});

test('dbops-query querylog prints compact rows', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/query/querylog/?limit=1&offset=0');
    sendJson(res, 200, {
      status: 0,
      total: 12,
      rows: [{
        id: 1053686,
        instance_name: 'prod-main',
        db_name: 'app_db',
        sqllog: 'SELECT * FROM tbl_demo',
        create_time: '2026-06-12 10:00:00',
        user_display: 'dev-a',
        noisy: 'omit',
      }],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['querylog', 'limit=1', 'offset=0'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.http_status, undefined);
    assert.equal(output.payload, undefined);
    assert.equal(output.total, 12);
    assert.equal(output.count, 1);
    assert.equal(output.items[0].id, 1053686);
    assert.equal(output.items[0].sql, 'SELECT * FROM tbl_demo');
    assert.equal(output.items[0].noisy, undefined);
  });
});

test('dbops-query favorites parses favorite options from dbops page', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/sqlquery/');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<select id="favorites"><option value="1">录播课营销-db</option><option value="2">other</option></select>');
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['favorite-find', '录播课'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.count, 1);
    assert.deepEqual(output.items, [{ id: '1', alias: '录播课营销-db' }]);
    assert.equal(output.http_status, undefined);
    assert.equal(output.content_type, undefined);
  });
});

test('dbops-query raw api keeps POST extension point', async () => {
  await withServer((req, res, body) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/favorite/');
    assert.deepEqual(parseForm(body), {
      query_log_id: '123',
      star: 'true',
      alias: 'test',
    });
    sendJson(res, 200, { status: 0, data: { ok: true } });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['api', 'POST', '/query/favorite/', 'query_log_id=123', 'star=true', 'alias=test'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.http_status, 200);
    assert.deepEqual(output.payload.data, { ok: true });
  });
});

test('dbops-query raw api redacts response payload', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/query/querylog/');
    sendJson(res, 200, {
      status: 0,
      data: {
        mobile: '13812345678',
        token: 'secret-token',
        nested: { accessKeySecret: 'ak-secret' },
      },
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['api', 'GET', '/query/querylog/'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /138\*\*\*\*5678/);
    assert.match(result.stdout, /"<redacted>"/);
    assert.doesNotMatch(result.stdout, /13812345678|secret-token|ak-secret/);
  });
});

test('dbops-query reports retryable HTTP errors with existing shape', async () => {
  await withServer((req, res) => {
    res.writeHead(503, { 'Content-Type': 'text/plain' });
    res.end('temporary unavailable');
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(['instances'], {
      ...fixtureEnv(serverUrl, configFile, cookieFile),
      DBOPS_HTTP_MAX_ATTEMPTS: '1',
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /\[service_error\] status=503 retryable: temporary unavailable/);
  });
});

test('dbops-query auth cookie helpers use final non-comment cookie line', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbops-query-cookie-'));
  const cookieFile = path.join(dir, 'dbops-auth-cookie.txt');
  fs.writeFileSync(cookieFile, [
    '# dbops auth cookie file',
    'old=value',
    '',
    '# replaced below',
    'sessionid=test-session; csrftoken=test-csrf',
    '',
  ].join('\n'));

  assert.equal(dbopsModule.readCookieFromFile(cookieFile), 'sessionid=test-session; csrftoken=test-csrf');
});

test('dbops-query auth success requires csrf and one auth cookie candidate', () => {
  assert.deepEqual(dbopsModule.missingRequiredCookies([
    { name: 'csrftoken', value: 'csrf' },
    { name: 'sessionid', value: 'session' },
  ]), []);

  assert.deepEqual(dbopsModule.missingRequiredCookies([
    { name: 'csrftoken', value: 'csrf' },
  ]), ['one of sessionid/internal_account_token/admin-authorization/authorization']);
});

test('dbops-query auth writes CRP-style cookie file without printing cookie', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbops-query-auth-'));
  const cookieFile = path.join(dir, 'dbops-auth-cookie.txt');
  const storageState = path.join(dir, 'dbops-auth-storage-state.json');
  const result = await dbopsModule.writeAuthFiles({
    baseUrl: 'https://dbops.codemao.cn',
    cookieFile,
    storageState,
  }, [
    { name: 'csrftoken', value: 'csrf', domain: 'dbops.codemao.cn', path: '/' },
    { name: 'sessionid', value: 'session', domain: 'dbops.codemao.cn', path: '/' },
  ]);

  assert.equal(result.cookie_file_path, cookieFile);
  assert.equal(result.cookie_count, 2);
  assert.deepEqual(result.cookie_names, ['csrftoken', 'sessionid']);
  const cookieText = fs.readFileSync(cookieFile, 'utf8');
  assert.match(cookieText, /# dbops auth cookie file/);
  assert.equal(dbopsModule.readCookieFromFile(cookieFile), 'csrftoken=csrf; sessionid=session');
  const state = JSON.parse(fs.readFileSync(storageState, 'utf8'));
  assert.equal(state.cookies.length, 2);
});

test('dbops-query browser auth lifecycle exits when the login tab is closed', () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const browser = new EventEmitter();
  context.pages = () => [page];
  context.browser = () => browser;
  const calls = [];

  const lifecycle = dbopsModule.installBrowserAuthCloseHandlers(context, (error) => {
    calls.push(error);
  });
  if (lifecycle.getPageCount() === 0) lifecycle.markPage(page);

  page.emit('close');

  assert.equal(calls.length, 1);
  assert.match(calls[0].message, /登录已取消或浏览器已关闭/);
});

test('dbops-query rejects query-on non-read-only SQL before authentication', () => {
  const result = runCli(['query-on', '实例', '库', 'UPDATE tbl_xxx SET name = 1']);

  assert.equal(result.status, 2);
  assert.match(result.stderr, /readonly_only/);
  assert.doesNotMatch(result.stderr, /cookie_missing/);
});
