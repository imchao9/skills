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
const contractTempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbops-query-contract-'));
const missingContractCookieFile = path.join(contractTempDir, 'missing-cookie.txt');

function contractCliEnv(env = {}) {
  return {
    ...process.env,
    DBOPS_COOKIE: '',
    DBOPS_CSRFTOKEN: '',
    DBOPS_COOKIE_FILE: missingContractCookieFile,
    CODEMAO_DBOPS_QUERY_TEST_BASE_URL: '',
    ...env,
  };
}

function runCli(args, env = {}, input = undefined) {
  return spawnSync(dbopsQuery, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    env: contractCliEnv(env),
    input,
  });
}

function runCliAsync(args, env = {}, input = '') {
  return new Promise((resolve, reject) => {
    const child = spawn(dbopsQuery, args, {
      cwd: skillRoot,
      env: contractCliEnv(env),
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

test('dbops-query contract CLI helper ignores inherited authentication', () => {
  const inheritedCookieFile = path.join(contractTempDir, 'inherited-cookie.txt');
  fs.writeFileSync(inheritedCookieFile, 'sessionid=inherited-session; csrftoken=inherited-csrf\n');
  const inherited = {
    DBOPS_COOKIE: process.env.DBOPS_COOKIE,
    DBOPS_CSRFTOKEN: process.env.DBOPS_CSRFTOKEN,
    DBOPS_COOKIE_FILE: process.env.DBOPS_COOKIE_FILE,
    NODE_ENV: process.env.NODE_ENV,
    CODEMAO_DBOPS_QUERY_TEST_BASE_URL: process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL,
  };
  process.env.DBOPS_COOKIE = 'sessionid=inherited-session; csrftoken=inherited-csrf';
  process.env.DBOPS_CSRFTOKEN = 'inherited-csrf';
  process.env.DBOPS_COOKIE_FILE = inheritedCookieFile;
  process.env.NODE_ENV = 'test';
  process.env.CODEMAO_DBOPS_QUERY_TEST_BASE_URL = 'http://127.0.0.1:0';

  try {
    const result = runCli(['instances']);

    assert.equal(result.status, 1);
    assert.match(result.stderr, /\[cookie_missing\]/);
    assert.doesNotMatch(result.stdout + result.stderr, /inherited-session|inherited-csrf/);
  } finally {
    for (const [key, value] of Object.entries(inherited)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('dbops-query subcommand help is specific and does not require authentication', () => {
  const cases = [
    [['auth', '--help'], /dbops-query auth \[--login-timeout SECONDS\]/, /Does not print cookie values/],
    [['query-on', '--help'], /dbops-query query-on "实例名" "库名"/, /Relational instances allow only SELECT, SHOW, and EXPLAIN/, /Redis and Mongo command text is passed to dbops/, /SHOW CREATE TABLE `table_name`/],
    [
      ['instances', '--help'],
      /dbops-query instances \[tag_code\] \[db_type TYPE\]/,
      /known_access lists the known subset confirmed by active approved applications/,
      /Other accessible instances or databases may be absent/,
      /Currently observed values: mongo, mysql, pgsql, redis/,
      /Other non-empty values are accepted/,
      /instances known_access db_type mysql/,
    ],
    [['resources', '--help'], /dbops-query resources "实例名" table db_name=库名/, /List databases, tables, or schemas/],
    [['querylog', '--help'], /dbops-query querylog \[limit=N\] \[offset=N\]/, /recent query logs/],
    [['queryloginfo', '--help'], /dbops-query queryloginfo <log_id>/, /query log detail/],
    [['favorites', '--help'], /dbops-query favorites/, /favorite queries/],
    [['favorite-list', '--help'], /Alias of dbops-query favorites/, /dbops-query favorite-list/],
    [['favorite-find', '--help'], /dbops-query favorite-find <keyword>/, /Search saved favorite/],
    [['favorite-info', '--help'], /dbops-query favorite-info <alias>/, /without running SQL/],
    [['favorite-run', '--help'], /dbops-query favorite-run <alias>/, /Confirm the target instance/],
    [['favorite-query', '--help'], /dbops-query favorite-query <alias>/, /Relational instances allow only SELECT, SHOW, and EXPLAIN/],
    [['favorite', '--help'], /dbops-query favorite <query_log_id> <alias>/, /changes favorite state/],
    [['unfavorite', '--help'], /dbops-query unfavorite <query_log_id>/, /changes favorite state/],
    [['api', '--help'], /dbops-query api GET \/path/, /POST may change state/],
  ];

  for (const [args, ...patterns] of cases) {
    const result = runCli(args);
    assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
    for (const pattern of patterns) assert.match(result.stdout, pattern, args.join(' '));
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

test('dbops-query instances rejects db_type without a value before loading config or cookie', () => {
  const result = runCli(['instances', 'can_read', 'db_type'], poisonedRuntimeEnv());

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\].*db_type requires a non-empty TYPE/);
  assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing/);
});

test('dbops-query instances rejects an empty db_type before loading config or cookie', () => {
  const result = runCli(['instances', 'can_read', 'db_type', ''], poisonedRuntimeEnv());

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\].*db_type requires a non-empty TYPE/);
  assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing/);
});

test('dbops-query instances rejects duplicate db_type before loading config or cookie', () => {
  const result = runCli(
    ['instances', 'can_read', 'db_type', 'mysql', 'db_type', 'redis'],
    poisonedRuntimeEnv(),
  );

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\].*duplicate db_type/);
  assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing/);
});

test('dbops-query instances rejects unknown query conditions before loading config or cookie', () => {
  const result = runCli(['instances', 'can_read', 'region', 'cn'], poisonedRuntimeEnv());

  assert.equal(result.status, 2);
  assert.match(result.stderr, /\[invalid_argument\].*unknown argument: region/);
  assert.doesNotMatch(result.stderr, /config_invalid_json|cookie_missing/);
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

test('dbops-query default target rejects relational non-read-only SQL before query request', async () => {
  let queryRequested = false;
  await withServer((req, res) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
      });
      return;
    }
    queryRequested = true;
    sendJson(res, 500, {});
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl, {
      instanceName: 'prod-main',
      dbName: 'app_db',
    });
    const result = await runCliAsync(['DESC tbl_xxx'], fixtureEnv(serverUrl, configFile, cookieFile));

    assert.equal(result.status, 2);
    assert.match(result.stderr, /readonly_only/);
    assert.equal(queryRequested, false);
  });
});

test('dbops-query rejects unsupported table definition commands and permits SHOW CREATE TABLE', () => {
  assert.doesNotThrow(() => dbopsModule.checkReadonlySql('SHOW CREATE TABLE tbl_xxx'));
  for (const sql of ['DESC tbl_xxx', 'DESCRIBE tbl_xxx']) {
    assert.throws(() => dbopsModule.checkReadonlySql(sql), { code: 'readonly_only' });
  }
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

test('dbops-query instances filters can_read instances by db_type without changing order', async () => {
  await withServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.url, '/group/user_all_instances/?tag_codes%5B%5D=can_read');
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'mysql-first', db_type: 'mysql', type: 'master' },
        { instance_name: 'redis-main', db_type: 'redis', type: 'master' },
        { instance_name: 'mysql-second', db_type: 'mysql', type: 'readonly' },
      ],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'can_read', 'db_type', 'mysql'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.deepEqual(output.items.map((item) => item.instance_name), ['mysql-first', 'mysql-second']);
  });
});

test('dbops-query instances accepts db_type with the default can_read tag', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/group/user_all_instances/?tag_codes%5B%5D=can_read');
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'mongo-main', db_type: 'mongo', type: 'master' },
        { instance_name: 'mysql-main', db_type: 'mysql', type: 'master' },
      ],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'db_type', 'mysql'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout).items.map((item) => item.instance_name), ['mysql-main']);
  });
});

test('dbops-query instances accepts a non-empty db_type outside the observed values', async () => {
  await withServer((req, res) => {
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'future-main', db_type: 'future-db', type: 'master' }],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'can_read', 'db_type', 'future-db'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout).items.map((item) => item.instance_name), ['future-main']);
  });
});

test('dbops-query instances known_access returns instances and databases confirmed by active applications', async () => {
  await withServer((req, res, body) => {
    if (req.url === '/query/applylist/') {
      assert.equal(req.method, 'POST');
      assert.deepEqual(parseForm(body), { limit: '50', offset: '0', search: '' });
      assert.equal(req.headers.referer, `${req.headers.origin}/queryapplylist/`);
      sendJson(res, 200, {
        total: 1,
        rows: [{
          apply_id: 2853,
          instance__instance_name: 'prod-main',
          db_list: 'app_db',
          status: 1,
          valid_date: '2099-05-26',
          create_time: '2026-05-26 16:34:57',
        }],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'prod-main', db_type: 'mysql', type: 'master' }],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(requests.length, 2);
    assert.equal(requests[1].method, 'GET');
    assert.equal(requests[1].url, '/group/user_all_instances/?tag_codes%5B%5D=can_read');
    assert.deepEqual(JSON.parse(result.stdout), {
      count: 1,
      items: [{
        instance_name: 'prod-main',
        db_type: 'mysql',
        type: 'master',
        known_access_databases: ['app_db'],
      }],
    });
  });
});

test('dbops-query instances known_access reports applylist service errors without requesting instances', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/query/applylist/');
    sendJson(res, 200, { status: 2, msg: 'applylist unavailable' });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 1);
    assert.match(result.stderr, /\[service_error\].*applylist unavailable/);
    assert.equal(requests.length, 1);
    assert.equal(result.stdout, '');
  });
});

test('dbops-query instances known_access merges databases from multiple applications in stable order', async () => {
  await withServer((req, res) => {
    if (req.url === '/query/applylist/') {
      sendJson(res, 200, {
        total: 3,
        rows: [
          {
            instance__instance_name: 'prod-main',
            db_list: 'codemaster,codemaster_wechat, market ',
            status: 1,
            valid_date: '2099-04-08',
            create_time: '2026-04-08 14:37:31',
          },
          {
            instance__instance_name: 'prod-main',
            db_list: 'market,analytics',
            status: 1,
            valid_date: '2099-03-01',
            create_time: '2026-03-01 10:00:00',
          },
          {
            instance__instance_name: 'other-main',
            db_list: 'other_db',
            status: 1,
            valid_date: '2099-02-01',
            create_time: '2026-02-01 10:00:00',
          },
        ],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'other-main', db_type: 'pgsql', type: 'master' },
        { instance_name: 'prod-main', db_type: 'mysql', type: 'master' },
      ],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.deepEqual(output.items.map((item) => item.instance_name), ['other-main', 'prod-main']);
    assert.deepEqual(output.items[1].known_access_databases, [
      'codemaster',
      'codemaster_wechat',
      'market',
      'analytics',
    ]);
  });
});

test('dbops-query instances known_access does not infer databases from table_list', async () => {
  await withServer((req, res) => {
    if (req.url === '/query/applylist/') {
      sendJson(res, 200, {
        total: 1,
        rows: [{
          instance__instance_name: 'table-only-main',
          db_list: '',
          table_list: 'app_db.tbl_demo',
          status: 1,
          valid_date: '2099-01-01',
        }],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'table-only-main', db_type: 'mysql', type: 'master' }],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout).items[0].known_access_databases, []);
  });
});

test('dbops-query instances known_access ignores unapproved applications and stops at the first expired approval', async () => {
  await withServer((req, res) => {
    if (req.url === '/query/applylist/') {
      sendJson(res, 200, {
        total: 4,
        rows: [
          {
            instance__instance_name: 'pending-main',
            db_list: 'pending_db',
            status: 0,
            valid_date: '2000-01-01',
            create_time: '2026-06-01 10:00:00',
          },
          {
            instance__instance_name: 'active-main',
            db_list: 'active_db',
            status: '1',
            valid_date: '2099-01-01',
            create_time: '2026-05-01 10:00:00',
          },
          {
            instance__instance_name: 'expired-main',
            db_list: 'expired_db',
            status: 1,
            valid_date: '2000-01-01',
            create_time: '2025-05-01 10:00:00',
          },
          {
            instance__instance_name: 'older-main',
            db_list: 'older_db',
            status: 1,
            valid_date: '2099-01-01',
            create_time: '2024-05-01 10:00:00',
          },
        ],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'pending-main', db_type: 'mysql', type: 'master' },
        { instance_name: 'active-main', db_type: 'mysql', type: 'master' },
        { instance_name: 'expired-main', db_type: 'mysql', type: 'master' },
        { instance_name: 'older-main', db_type: 'mysql', type: 'master' },
      ],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout).items.map((item) => item.instance_name), ['active-main']);
  });
});

test('dbops-query instances known_access does not request another page after an expired approval', async () => {
  await withServer((req, res) => {
    if (req.url === '/query/applylist/') {
      sendJson(res, 200, {
        total: 100,
        rows: [
          { status: 1, valid_date: '2099-01-01', instance__instance_name: 'active-main', db_list: 'active_db' },
          { status: 1, valid_date: '2000-01-01', instance__instance_name: 'expired-main', db_list: 'expired_db' },
          ...Array.from({ length: 48 }, (_, index) => ({
            status: 0,
            valid_date: '2099-01-01',
            instance__instance_name: `pending-${index}`,
            db_list: `pending_db_${index}`,
          })),
        ],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'active-main', db_type: 'mysql', type: 'master' }],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(requests.filter((request) => request.url === '/query/applylist/').length, 1);
  });
});

test('dbops-query instances known_access skips the instance request when no active application exists', async () => {
  await withServer((req, res) => {
    assert.equal(req.url, '/query/applylist/');
    sendJson(res, 200, {
      total: 2,
      rows: [
        { status: 0, valid_date: '2099-01-01', instance__instance_name: 'pending-main', db_list: 'pending_db' },
        { status: 1, valid_date: '2000-01-01', instance__instance_name: 'expired-main', db_list: 'expired_db' },
      ],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(requests.length, 1);
    assert.deepEqual(JSON.parse(result.stdout), { count: 0, items: [] });
  });
});

test('dbops-query instances known_access reads active applications across pages', async () => {
  await withServer((req, res, body) => {
    if (req.url === '/query/applylist/') {
      const { offset } = parseForm(body);
      if (offset === '0') {
        sendJson(res, 200, {
          rows: Array.from({ length: 50 }, (_, index) => ({
            status: 1,
            valid_date: '2099-01-01',
            instance__instance_name: `page-one-${index}`,
            db_list: `db_${index}`,
          })),
        });
        return;
      }
      assert.equal(offset, '50');
      sendJson(res, 200, {
        rows: [{
          status: 1,
          valid_date: '2099-01-01',
          instance__instance_name: 'page-two-main',
          db_list: 'page_two_db',
        }],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'page-two-main', db_type: 'mysql', type: 'master' }],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(requests.map((request) => request.url), [
      '/query/applylist/',
      '/query/applylist/',
      '/group/user_all_instances/?tag_codes%5B%5D=can_read',
    ]);
    assert.deepEqual(JSON.parse(result.stdout).items[0].known_access_databases, ['page_two_db']);
  });
});

test('dbops-query instances known_access reads at most 500 applications', async () => {
  await withServer((req, res, body) => {
    if (req.url === '/query/applylist/') {
      const { offset } = parseForm(body);
      sendJson(res, 200, {
        total: 1000,
        rows: Array.from({ length: 50 }, (_, index) => ({
          status: 1,
          valid_date: '2099-01-01',
          instance__instance_name: 'bounded-main',
          db_list: `db_${Number(offset) + index}`,
        })),
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [{ instance_name: 'bounded-main', db_type: 'mysql', type: 'master' }],
    });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    const applyRequests = requests.filter((request) => request.url === '/query/applylist/');
    assert.equal(applyRequests.length, 10);
    assert.deepEqual(applyRequests.map((request) => parseForm(request.body).offset), [
      '0', '50', '100', '150', '200', '250', '300', '350', '400', '450',
    ]);
    assert.equal(JSON.parse(result.stdout).items[0].known_access_databases.length, 500);
  });
});

test('dbops-query instances known_access filters can_read metadata by db_type before intersecting applications', async () => {
  await withServer((req, res) => {
    if (req.url === '/query/applylist/') {
      sendJson(res, 200, {
        total: 2,
        rows: [
          { status: 1, valid_date: '2099-01-01', instance__instance_name: 'redis-main', db_list: 'cache_db' },
          { status: 1, valid_date: '2099-01-01', instance__instance_name: 'mysql-main', db_list: 'app_db' },
        ],
      });
      return;
    }
    sendJson(res, 200, {
      status: 0,
      data: [
        { instance_name: 'redis-main', db_type: 'redis', type: 'master' },
        { instance_name: 'mysql-main', db_type: 'mysql', type: 'master' },
      ],
    });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['instances', 'known_access', 'db_type', 'mysql'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout).items, [{
      instance_name: 'mysql-main',
      db_type: 'mysql',
      type: 'master',
      known_access_databases: ['app_db'],
    }]);
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

test('dbops-query query-on passes a Redis command to dbops', async () => {
  await withServer((req, res, body) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'cache-main', db_type: 'redis', type: 'master' }],
      });
      return;
    }
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/query/');
    const form = parseForm(body);
    assert.equal(form.instance_name, 'cache-main');
    assert.equal(form.sql_content, 'GET cache_key');
    sendJson(res, 200, { status: 0, data: { column_list: [], rows: [] } });
  }, async (serverUrl) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const result = await runCliAsync(
      ['query-on', 'cache-main', '0', 'GET cache_key'],
      fixtureEnv(serverUrl, configFile, cookieFile),
    );

    assert.equal(result.status, 0, result.stderr);
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

test('dbops-query default target passes Redis and Mongo commands to dbops', async () => {
  for (const [dbType, query] of [
    ['redis', 'GET cache_key'],
    ['mongo', 'db.users.find({})'],
  ]) {
    await withServer((req, res, body) => {
      if (req.url.startsWith('/group/user_all_instances/')) {
        sendJson(res, 200, {
          status: 0,
          data: [{ instance_name: 'data-main', db_type: dbType, type: 'master' }],
        });
        return;
      }
      assert.equal(req.method, 'POST');
      assert.equal(req.url, '/query/');
      assert.equal(parseForm(body).sql_content, query);
      sendJson(res, 200, { status: 0, data: { column_list: [], rows: [] } });
    }, async (serverUrl) => {
      const { configFile, cookieFile } = writeFixtureFiles(serverUrl, {
        instanceName: 'data-main',
        dbName: 'app_db',
      });
      const result = await runCliAsync([query], fixtureEnv(serverUrl, configFile, cookieFile));

      assert.equal(result.status, 0, result.stderr);
    });
  }
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

test('dbops-query preauthorizes DingTalk local network access without making it required', async () => {
  const calls = [];
  assert.equal(await dbopsModule.grantDingTalkLocalNetworkAccess({
    grantPermissions: async (...args) => calls.push(args),
  }), true);
  assert.deepEqual(calls, [[['local-network-access'], { origin: 'https://login.dingtalk.com' }]]);
  assert.equal(await dbopsModule.grantDingTalkLocalNetworkAccess({
    grantPermissions: async () => { throw new Error('unsupported'); },
  }), false);
});

test('dbops-query rejects relational writes before sending the query request', async () => {
  await withServer((req, res) => {
    if (req.url.startsWith('/group/user_all_instances/')) {
      sendJson(res, 200, {
        status: 0,
        data: [{ instance_name: 'fake-instance', db_type: 'mysql' }],
      });
      return;
    }
    sendJson(res, 200, { status: 0, data: { column_list: [], rows: [] } });
  }, async (serverUrl, requests) => {
    const { configFile, cookieFile } = writeFixtureFiles(serverUrl);
    const env = fixtureEnv(serverUrl, configFile, cookieFile);

    for (const sql of ['UPDATE tbl_xxx SET name = 1', 'DESC tbl_xxx', 'DESCRIBE tbl_xxx']) {
      const result = await runCliAsync(['query-on', 'fake-instance', 'fake-db', sql], env);

      assert.equal(result.status, 2, `${sql}\n${result.stderr}`);
      assert.match(result.stderr, /\[readonly_only\]/);
    }

    const metadataRequests = requests.filter((request) => request.url.startsWith('/group/user_all_instances/'));
    const queryRequests = requests.filter((request) => request.url === '/query/');
    assert.equal(requests.length, 3);
    assert.equal(metadataRequests.length, 3);
    assert.equal(queryRequests.length, 0);
  });
});
