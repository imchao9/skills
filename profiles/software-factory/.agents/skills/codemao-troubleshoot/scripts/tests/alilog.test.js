#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const EventEmitter = require('node:events');
const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const fsPromises = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const {
  parseArgs,
  parseTime,
  parseTimeExpression,
  buildQueryBody,
  buildLogstoresRequest,
  buildIndexFieldsRequest,
  parseIndexFieldsResponse,
  getIndexFieldsWithAuthFile,
  queryLogsWithAuthFile,
  listLogstoresWithAuthFile,
  formatIndexFieldsOutput,
  normalizeResult,
  isSuccessfulQueryOutput,
  extractPayloadLogs,
  formatQueryOutput,
  formatFieldsOutput,
  formatLogstoresOutput,
  detectAliyunCaptchaInDocument,
  detectAliyunFeedbackInDocument,
  autoLoginActionForState,
  autoLoginPacingRange,
  chooseAliyunAutoLoginDelay,
  loginAutoFillGuidanceMessage,
  shouldInjectLoginGuidanceNotice,
  openLoginPage,
  reportAutoFillFailure,
  runAliyunLoginAutomation,
  runAliyunAutoFillMonitor,
  hasAliyunCaptcha,
  getAliyunFeedback,
  fetchWithTimeout,
  findPlaywrightModulePath,
  writeAuthFile,
  captureSlsAuth,
  captureAuthWithBrowser,
  installBrowserAuthCloseHandlers,
  formatAuthSuccessOutput,
  applyUserConfig,
  readUsernameFromKeychainAccount,
  readPasswordFromKeychain,
  readTotpSeedFromKeychain,
  parseSupportedTotpSeed,
  canUseHeadlessAliyunLogin,
  selectAliyunAuthMode,
  runAuth,
  runAuthWorkerProcess,
} = require('../alilog');

const longContent = `${'a'.repeat(1300)}continued tail`;
const foreignOriginHandoffNotice = 'auth: 自动填充已暂停：页面已离开支持的阿里云登录地址。请在浏览器中手动完成登录；成功后仍会自动保存认证。';
const sqlContent = [
  'business before',
  'Creating a new SqlSession',
  '==>  Preparing: select * from users where id = ?',
  '==> Parameters: 1(Long)',
  '<==    Columns: id, name',
  '<==        Row: 1, alice',
  '<==      Total: 1',
  '<==    Updates: 1',
  'Closing non transactional SqlSession',
  'business after',
].join('\n');

function raw(logs) {
  return {
    success: true,
    data: { logs },
  };
}

function output(logs) {
  return {
    scope: {},
    response: { status: 200, ok: true },
    result: normalizeResult(raw(logs)),
  };
}

function args(extra = {}) {
  return {
    raw: false,
    selectFields: [],
    extraFields: [],
    expandSql: false,
    continueAt: '',
    ...extra,
  };
}

function queryArgs(extra = []) {
  return parseArgs([
    'query',
    '--project', 'proj',
    '--logstore', 'store',
    '--query', '*',
    '--from', '2026-06-01 14:00:00',
    '--to', '2026-06-01 14:05:00',
    ...extra,
  ]);
}

function fieldsArgs(extra = []) {
  return parseArgs([
    'fields',
    '--project', 'proj',
    '--logstore', 'store',
    '--query', '*',
    '--time', 'last_15m',
    ...extra,
  ]);
}

function indexFieldsArgs(extra = []) {
  return parseArgs([
    'index-fields',
    '--project', 'proj',
    '--logstore', 'store',
    ...extra,
  ]);
}

function assertThrowsMessage(fn, pattern) {
  assert.throws(fn, (error) => pattern.test(error.message));
}

test('index-fields accepts only its required project and logstore target', () => {
  const parsed = indexFieldsArgs();

  assert.strictEqual(parsed.command, 'index-fields');
  assert.strictEqual(parsed.project, 'proj');
  assert.strictEqual(parsed.logstore, 'store');
  assertThrowsMessage(() => parseArgs(['index-fields', '--logstore', 'store']), /--project is required/);
  assertThrowsMessage(() => parseArgs(['index-fields', '--project', 'proj']), /--logstore is required/);
  assertThrowsMessage(() => indexFieldsArgs(['--query', '*']), /unknown argument: --query/);
});

test('index-fields is discoverable from top-level and command help without unrelated options', () => {
  const scriptPath = path.resolve(__dirname, '..', 'alilog');
  const topHelp = execFileSync(process.execPath, [scriptPath, '--help'], { encoding: 'utf8' });
  const commandHelp = execFileSync(process.execPath, [scriptPath, 'index-fields', '--help'], { encoding: 'utf8' });

  assert.match(topHelp, /scripts\/alilog index-fields --project PROJECT --logstore LOGSTORE/);
  assert.match(topHelp, /index-fields\s+get the current logstore index configuration/);
  assert.match(commandHelp, /^usage: scripts\/alilog index-fields --project PROJECT --logstore LOGSTORE/m);
  assert.doesNotMatch(commandHelp, /--query|--time|--page|--raw|--details|--compact/);
});

test('index-fields CLI reports missing required targets on stderr with a nonzero status', () => {
  const scriptPath = path.resolve(__dirname, '..', 'alilog');
  const result = spawnSync(process.execPath, [scriptPath, 'index-fields', '--project', 'proj'], {
    encoding: 'utf8',
  });

  assert.notStrictEqual(result.status, 0);
  assert.strictEqual(result.stdout, '');
  assert.match(result.stderr, /^ERROR: --logstore is required/m);
});

test('index-fields builds the canonical encoded console request', () => {
  const url = new URL(buildIndexFieldsRequest({
    project: 'project_name',
    logstore: 'log-store',
  }));

  assert.strictEqual(url.origin, 'https://sls.console.aliyun.com');
  assert.strictEqual(url.pathname, '/console/logstoreindex/getString.json');
  assert.deepStrictEqual([...url.searchParams.entries()], [
    ['ProjectName', 'project_name'],
    ['LogStoreName', 'log-store'],
  ]);
});

test('index-fields unwraps string data and removes only known top-level noise', () => {
  const config = parseIndexFieldsResponse({
    code: '200',
    success: true,
    message: 'successful',
    requestId: 'request-id',
    data: JSON.stringify({
      index_mode: 'v2',
      storage: 'pg',
      log_reduce: true,
      log_reduce_white_list: ['keep-out'],
      log_reduce_black_list: ['keep-out'],
      ttl: 30,
      keys: {
        nested: {
          storage: 'field-metadata',
          log_reduce: false,
        },
      },
    }),
  });

  assert.deepStrictEqual(config, {
    index_mode: 'v2',
    ttl: 30,
    keys: {
      nested: {
        storage: 'field-metadata',
        log_reduce: false,
      },
    },
  });
});

test('index-fields prunes empty object properties without changing array elements or meaningful falsy values', () => {
  const config = parseIndexFieldsResponse({
    success: true,
    data: {
      empty: '',
      absent: null,
      enabled: false,
      zero: 0,
      unlimited: -1,
      empty_array: [],
      empty_object: {},
      values: ['', null, false, 0, { alias: '', keep: 'yes' }],
      nested: {
        alias: '',
        embedding: null,
        after_pruning: { empty: '' },
      },
    },
  });

  assert.deepStrictEqual(config, {
    enabled: false,
    zero: 0,
    unlimited: -1,
    empty_array: [],
    empty_object: {},
    values: ['', null, false, 0, { keep: 'yes' }],
    nested: { after_pruning: {} },
  });
});

test('index-fields preserves __proto__ as an inert field name without prototype pollution', () => {
  const raw = JSON.parse('{"keys":{"__proto__":{"type":"text","token":[]}}}');
  const config = parseIndexFieldsResponse({ success: true, data: JSON.stringify(raw) });

  assert.strictEqual(Object.hasOwn(config.keys, '__proto__'), true);
  assert.deepStrictEqual(config.keys.__proto__, { type: 'text', token: [] });
  assert.strictEqual(Object.getPrototypeOf(config.keys), Object.prototype);
  assert.strictEqual(Object.prototype.type, undefined);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(config)), raw);
});

test('index-fields preserves official text numeric JSON full-text vector and unknown index structure', () => {
  const config = parseIndexFieldsResponse({
    success: true,
    data: {
      index_mode: 'v2',
      ttl: 30,
      lastModifyTime: 1784240300,
      max_text_len: 2048,
      line: {
        caseSensitive: false,
        chn: false,
        token: [],
        include_keys: ['content'],
      },
      keys: {
        message: { type: 'text', doc_value: false, alias: '', token: [] },
        status: { type: 'long', doc_value: true },
        elapsed: { type: 'double', doc_value: true, alias: 'duration' },
        payload: {
          type: 'json',
          doc_value: true,
          index_all: false,
          max_depth: -1,
          json_keys: {
            token_de_base64: {
              type: 'json',
              json_keys: {
                nested: {
                  type: 'text',
                  embedding: 'embedding-config',
                  vector_index: 'vector-config',
                },
              },
            },
          },
        },
      },
      scan_index: { enabled: false },
      future_capability: { mode: 'kept' },
    },
  });

  assert.deepStrictEqual(config.keys.message, { type: 'text', doc_value: false, token: [] });
  assert.deepStrictEqual(config.keys.status, { type: 'long', doc_value: true });
  assert.deepStrictEqual(config.keys.elapsed, { type: 'double', doc_value: true, alias: 'duration' });
  assert.strictEqual(config.keys.payload.json_keys.token_de_base64.json_keys.nested.embedding, 'embedding-config');
  assert.strictEqual(config.keys.payload.json_keys.token_de_base64.json_keys.nested.vector_index, 'vector-config');
  assert.strictEqual(config.keys.payload.max_depth, -1);
  assert.deepStrictEqual(config.line, {
    caseSensitive: false,
    chn: false,
    token: [],
    include_keys: ['content'],
  });
  assert.deepStrictEqual(config.scan_index, { enabled: false });
  assert.deepStrictEqual(config.future_capability, { mode: 'kept' });
});

test('index-fields does not invent a missing full-text line configuration', () => {
  const config = parseIndexFieldsResponse({ success: true, data: { keys: {} } });

  assert.strictEqual(Object.hasOwn(config, 'line'), false);
});

test('index-fields reuses saved auth for a read-only GET and returns one compact JSON line', async () => {
  let requestUrl;
  let requestOptions;
  const config = await getIndexFieldsWithAuthFile(indexFieldsArgs(), {
    readAuthFile: async () => ({
      cookie: 'secret-cookie',
      csrf_token: 'secret-csrf',
      referer: 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store',
    }),
    fetchWithTimeout: async (url, options) => {
      requestUrl = url;
      requestOptions = options;
      return {
        status: 200,
        ok: true,
        async text() {
          return JSON.stringify({
            success: true,
            data: JSON.stringify({ index_mode: 'v2', keys: {} }),
          });
        },
      };
    },
  });

  const url = new URL(requestUrl);
  assert.strictEqual(url.pathname, '/console/logstoreindex/getString.json');
  assert.strictEqual(url.searchParams.get('ProjectName'), 'proj');
  assert.strictEqual(url.searchParams.get('LogStoreName'), 'store');
  assert.strictEqual(requestOptions.method, 'GET');
  assert.strictEqual(requestOptions.headers.cookie, 'secret-cookie');
  assert.strictEqual(requestOptions.headers['x-csrf-token'], 'secret-csrf');
  assert.strictEqual(requestOptions.headers.referer, 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store');
  assert.strictEqual(formatIndexFieldsOutput(config), '{"index_mode":"v2","keys":{}}');
  assert.doesNotMatch(formatIndexFieldsOutput(config), /secret-cookie|secret-csrf|proj|store/);
  assert.doesNotMatch(formatIndexFieldsOutput(config), /\n/);
});

test('index-fields maps missing auth and HTTP authentication failures to one safe recovery action', async () => {
  const target = indexFieldsArgs();
  await assert.rejects(
    getIndexFieldsWithAuthFile(target, {
      readAuthFile: async () => { throw new Error('/secret/auth/path'); },
    }),
    { message: 'auth expired or invalid; run scripts/alilog auth' },
  );

  for (const status of [401, 403]) {
    await assert.rejects(
      getIndexFieldsWithAuthFile(target, {
        readAuthFile: async () => ({ cookie: 'secret', csrf_token: 'secret' }),
        fetchWithTimeout: async () => ({
          status,
          ok: false,
          async text() { return '<html>login</html>'; },
        }),
      }),
      { message: 'auth expired or invalid; run scripts/alilog auth' },
    );
  }
});

test('index-fields rejects unsafe or malformed response shapes without echoing upstream payloads', async () => {
  const invalidData = [
    [undefined, /data must be an object/],
    [null, /data must be an object/],
    [[], /data must be an object/],
    [42, /data must be an object/],
    ['not-json', /data is not valid JSON/],
    ['null', /data must be an object/],
    ['[]', /data must be an object/],
  ];
  for (const [data, expected] of invalidData) {
    assertThrowsMessage(
      () => parseIndexFieldsResponse({ success: true, data }),
      expected,
    );
  }
  assertThrowsMessage(
    () => parseIndexFieldsResponse({ success: false, message: 'secret upstream detail' }),
    /^index request failed: success=false$/,
  );

  const target = indexFieldsArgs();
  const execute = (status, ok, body) => getIndexFieldsWithAuthFile(target, {
    readAuthFile: async () => ({ cookie: 'secret-cookie', csrf_token: 'secret-csrf' }),
    fetchWithTimeout: async () => ({
      status,
      ok,
      async text() { return body; },
    }),
  });
  await assert.rejects(execute(200, true, 'not-json'), {
    message: 'invalid index response: response is not valid JSON',
  });
  await assert.rejects(execute(500, false, JSON.stringify({ success: false, message: 'secret upstream detail' })), {
    message: 'index request failed: status=500',
  });
  for (const payload of [
    { code: 'ConsoleNeedLogin', success: false },
    { message: 'ConsoleNeedLogin', success: false },
  ]) {
    await assert.rejects(execute(200, true, JSON.stringify(payload)), {
      message: 'auth expired or invalid; run scripts/alilog auth',
    });
  }
});

function keychainArgs(extra = {}) {
  return {
    command: 'auth',
    userFile: '/tmp/alilog-user.json',
    username: '',
    keychainService: 'alilog',
    totpKeychainService: 'alilog-totp',
    ...extra,
  };
}

function captchaElement(extra = {}) {
  return {
    textContent: '',
    href: '',
    src: '',
    visible: true,
    getAttribute(name) {
      if (name === 'aria-hidden') return this.ariaHidden ? 'true' : '';
      if (name === 'href') return this.href;
      if (name === 'src') return this.src;
      return '';
    },
    closest(selector) {
      return selector === '[aria-hidden="true"]' && this.hiddenByAria ? this : null;
    },
    ...extra,
  };
}

function captchaDocument(elementsBySelector) {
  return {
    querySelector(selector) {
      const elements = elementsBySelector[selector];
      return Array.isArray(elements) ? elements[0] || null : elements || null;
    },
    querySelectorAll(selector) {
      const elements = elementsBySelector[selector];
      if (!elements) return [];
      return Array.isArray(elements) ? elements : [elements];
    },
  };
}

function detectCaptcha(elementsBySelector) {
  return detectAliyunCaptchaInDocument(
    captchaDocument(elementsBySelector),
    (element) => Boolean(element && element.visible),
    (element) => String(element && element.textContent ? element.textContent : ''),
    (element) => String(element && (element.href || element.src || element.getAttribute('href') || element.getAttribute('src')) || ''),
  );
}

function detectAliyunFeedback(elementsBySelector) {
  return detectAliyunFeedbackInDocument(
    captchaDocument(elementsBySelector),
    (element) => Boolean(element && element.visible),
    (element) => String(element && element.textContent ? element.textContent : ''),
    (element) => String(element && (element.href || element.src || element.getAttribute('href') || element.getAttribute('src')) || ''),
  );
}

function fakeCaptchaFrame(elementsBySelector) {
  return {
    async evaluate(pageFunction, detectorSource) {
      const resolvedElements = typeof elementsBySelector === 'function' ? elementsBySelector() : elementsBySelector;
      const detector = (0, eval)(`(${detectorSource})`);
      return detector(
        captchaDocument(resolvedElements),
        (element) => Boolean(element && element.visible),
        (element) => String(element && element.textContent ? element.textContent : ''),
        (element) => String(element && (
          element.getAttribute('href')
          || element.href
          || element.getAttribute('src')
          || element.src
        ) || ''),
      );
    },
  };
}

function fakeInput(value = '') {
  return {
    value,
    visible: true,
    fills: [],
    fillTimes: [],
    first() {
      return this;
    },
    async isVisible() {
      return this.visible;
    },
    async inputValue() {
      return this.value;
    },
    async click() {
    },
    async fill(nextValue) {
      this.value = String(nextValue);
      this.fills.push(String(nextValue));
      this.fillTimes.push(Date.now());
    },
  };
}

function fakeLoginPage(elementsBySelector, options = {}) {
  const frame = {};
  const listeners = new Map();
  let waitCount = 0;
  let currentUrl = options.url || 'https://signin.aliyun.com/example/login.htm#/main';
  function emit(event, value) {
    for (const listener of listeners.get(event) || []) {
      listener(value);
    }
  }
  const page = {
    on(event, listener) {
      const eventListeners = listeners.get(event) || [];
      eventListeners.push(listener);
      listeners.set(event, eventListeners);
    },
    off(event, listener) {
      const eventListeners = listeners.get(event) || [];
      listeners.set(event, eventListeners.filter((item) => item !== listener));
    },
    mainFrame() {
      return frame;
    },
    url() {
      return waitCount >= (options.loggedInAfterWaits || 2)
        ? 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store'
        : currentUrl;
    },
    frames() {
      if (typeof options.frames === 'function') return options.frames(waitCount, this, currentUrl);
      if (options.frames) return options.frames;
      return [this];
    },
    locator(selector) {
      const element = elementsBySelector[selector] || {
        first() {
          return this;
        },
        async isVisible() {
          return false;
        },
      };
      return element;
    },
    gotoUrls: [],
    waitDurations: [],
    injectedNotices: [],
    injectedNoticeSources: [],
    async evaluate(pageFunction, arg) {
      if (options.evaluate) return options.evaluate(pageFunction, arg, this);
      if (String(pageFunction).includes('alilog-login-guidance-notice')) {
        this.injectedNotices.push(String(arg || ''));
        this.injectedNoticeSources.push(String(pageFunction));
        return undefined;
      }
      return false;
    },
    async goto(url) {
      if (options.goto) return options.goto(url, this);
      this.gotoUrls.push(url);
      this.setUrl(url);
    },
    async waitForTimeout(ms) {
      waitCount += 1;
      this.waitDurations.push(ms);
      if (options.advanceTime) options.advanceTime(ms);
      if (options.afterWait) options.afterWait(waitCount, this);
    },
    setUrl(url) {
      currentUrl = url;
      emit('framenavigated', frame);
    },
  };
  return page;
}

function fakeAliyunLoginPage(initialState, transitions) {
  let state = initialState;
  const actions = [];
  const waits = [];
  const observedStates = [];
  const username = fakeInput('');
  const password = fakeInput('');
  const totp = fakeInput('');

  function visibleInput(selector) {
    if (state === 'username' && selector === '#loginName') return username;
    if ((state === 'password' || state === 'password-rejected') && selector === '#loginPassword') return password;
    if ((state === 'totp' || state === 'totp-rejected') && selector === 'input[placeholder="请输入 6 位数字安全码"]') return totp;
    return null;
  }

  function actionForRole(name) {
    const matches = (label) => name instanceof RegExp ? name.test(label) : String(name) === label;
    if (state === 'username' && matches('下一步')) return 'next';
    if ((state === 'password' || state === 'password-rejected') && matches('登录')) return 'password-submit';
    if ((state === 'totp' || state === 'totp-rejected') && matches('提交验证')) return 'totp-submit';
    return '';
  }

  function actionForText(pattern) {
    const value = String(pattern);
    if (state === 'password-choice' && /使用密码登录/.test(value)) return 'password-mode';
    if (state === 'virtual-mfa' && /虚拟/.test(value)) return 'virtual-mfa';
    return '';
  }

  function actionLocator(action) {
    return {
      first() {
        return this;
      },
      async isVisible() {
        return Boolean(action);
      },
      async click() {
        actions.push(action);
        state = transitions[action] || state;
      },
    };
  }

  function documentForState() {
    const alert = state === 'password-rejected'
      ? captchaElement({ textContent: '用户名或密码错误，还可以重试4次 RequestId：ignored' })
      : state === 'totp-rejected'
        ? captchaElement({ textContent: '安全码错误。查看原因 RequestId：ignored' })
        : state === 'unknown-rejected'
          ? captchaElement({ textContent: '当前登录状态无法继续，请稍后再试' })
        : null;
    return captchaDocument({
      '[role="alert"].next-message-error': alert,
      '#nocaptcha.nc-container': state === 'captcha' ? captchaElement() : null,
    });
  }

  return {
    actions,
    waits,
    observedStates,
    username,
    password,
    totp,
    url() {
      return state === 'sls-console'
        ? 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store'
        : 'https://signin.aliyun.com/example/login.htm#/main';
    },
    frames() {
      return [this];
    },
    locator(selector) {
      const input = visibleInput(selector);
      return input || {
        first() {
          return this;
        },
        async isVisible() {
          return false;
        },
      };
    },
    getByRole(role, options = {}) {
      return actionLocator(role === 'button' ? actionForRole(options.name) : '');
    },
    getByText(pattern) {
      return actionLocator(actionForText(pattern));
    },
    async evaluate(pageFunction, detectorSource) {
      observedStates.push(state);
      const detector = (0, eval)(`(${detectorSource})`);
      return detector(
        documentForState(),
        (element) => Boolean(element && element.visible),
        (element) => String(element && element.textContent ? element.textContent : ''),
        (element) => String(element && (element.href || element.src || element.getAttribute('href') || element.getAttribute('src')) || ''),
      );
    },
    async waitForTimeout(ms) {
      waits.push(ms);
      if (this.advanceTime) this.advanceTime(ms);
      const nextState = Array.isArray(transitions.__afterWait)
        ? transitions.__afterWait.shift()
        : transitions.__afterWait;
      if (nextState) {
        state = nextState;
      } else if (state === 'unknown' && transitions.__onWait) {
        state = Array.isArray(transitions.__onWait)
          ? transitions.__onWait.shift()
          : transitions.__onWait;
      }
    },
  };
}

async function withFakeNow(start, fn) {
  const originalNow = Date.now;
  let now = start;
  Date.now = () => now;
  try {
    return await fn((ms) => {
      now += ms;
    });
  } finally {
    Date.now = originalNow;
  }
}

async function captureConsoleLogs(fn) {
  const originalLog = console.log;
  const lines = [];
  console.log = (...values) => lines.push(values.join(' '));
  try {
    await fn();
    return lines;
  } finally {
    console.log = originalLog;
  }
}

test('extractPayloadLogs supports documented response shapes', () => {
  const logs = [{ content: 'x' }];
  assert.strictEqual(extractPayloadLogs({ logs }), logs);
  assert.strictEqual(extractPayloadLogs({ data: { logs } }), logs);
  assert.strictEqual(extractPayloadLogs({ data: logs }), logs);
  assert.strictEqual(extractPayloadLogs({ items: logs }), logs);
  assert.strictEqual(extractPayloadLogs({ results: logs }), logs);
});

test('nested raw.data.logs default output includes container and content', () => {
  const text = formatQueryOutput(output([
    { __time__: '1765450000', _container_name_: 'rocket-ai-genie', content: 'hello nested log' },
  ]), args());

  assert.notStrictEqual(text, 'no logs');
  assert.doesNotMatch(text, /\[1\] time=/);
  assert.match(text, /rocket-ai-genie/);
  assert.match(text, /hello nested log/);
});

test('normalizeResult count handles nested data.logs', () => {
  assert.strictEqual(normalizeResult(raw([{ content: 'a' }, { content: 'b' }])).count, 2);
});

test('query output success helper distinguishes SLS errors from empty results', () => {
  assert.equal(isSuccessfulQueryOutput(output([])), true);
  assert.equal(isSuccessfulQueryOutput({
    response: { status: 200, ok: true },
    result: normalizeResult({ success: false, code: 'ParameterInvalid', message: 'syntax error' }),
  }), false);
  assert.equal(isSuccessfulQueryOutput({
    response: { status: 401, ok: false },
    result: null,
  }), false);
});

test('query and fields reject a successful HTTP response whose body is not JSON without echoing it', async () => {
  for (const targetArgs of [queryArgs(), fieldsArgs()]) {
    for (const privateBody of [
      '<html>private login response apiKey=private-key</html>',
      '',
    ]) {
      await assert.rejects(
        queryLogsWithAuthFile(targetArgs, {
          readAuthFile: async () => ({
            cookie: 'private-cookie',
            csrf_token: 'private-csrf',
          }),
          fetchWithTimeout: async () => ({
            status: 200,
            ok: true,
            async text() {
              return privateBody;
            },
          }),
        }),
        (error) => {
          assert.strictEqual(
            error.message,
            `invalid ${targetArgs.command} response: response is not valid JSON`,
          );
          assert.doesNotMatch(error.message, /private|html|apiKey/i);
          return true;
        },
      );
    }
  }
});

test('query maps HTTP and payload login failures to the same safe auth recovery action', async () => {
  const execute = (status, ok, body) => queryLogsWithAuthFile(queryArgs(), {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status,
      ok,
      async text() {
        return body;
      },
    }),
  });

  for (const invocation of [
    () => execute(401, false, '<html>private login response</html>'),
    () => execute(403, false, ''),
    () => execute(200, true, JSON.stringify({ success: false, code: 'ConsoleNeedLogin' })),
    () => execute(200, true, JSON.stringify({ success: false, message: 'ConsoleNeedLogin' })),
  ]) {
    await assert.rejects(invocation(), {
      message: 'auth expired or invalid; run scripts/alilog auth',
    });
  }
});

test('query, fields, and logstores classify HTTP auth failures before reading the response body', async () => {
  const targets = [
    (status, responseText) => queryLogsWithAuthFile(queryArgs(), {
      readAuthFile: async () => ({ cookie: 'private-cookie', csrf_token: 'private-csrf' }),
      fetchWithTimeout: async () => ({ status, ok: false, text: responseText }),
    }),
    (status, responseText) => queryLogsWithAuthFile(fieldsArgs(), {
      readAuthFile: async () => ({ cookie: 'private-cookie', csrf_token: 'private-csrf' }),
      fetchWithTimeout: async () => ({ status, ok: false, text: responseText }),
    }),
    (status, responseText) => listLogstoresWithAuthFile({
      project: 'proj',
      keyword: '',
      page: 1,
      pageSize: 18,
    }, {
      readAuthFile: async () => ({ cookie: 'private-cookie', csrf_token: 'private-csrf' }),
      fetchWithTimeout: async () => ({ status, ok: false, text: responseText }),
    }),
  ];

  for (const execute of targets) {
    for (const status of [401, 403]) {
      let bodyReads = 0;
      await assert.rejects(
        execute(status, async () => {
          bodyReads += 1;
          throw new Error('private login response must not be read');
        }),
        { message: 'auth expired or invalid; run scripts/alilog auth' },
      );
      assert.strictEqual(bodyReads, 0);
    }
  }
});

test('query and fields reject HTTP and business failures with command-specific safe errors', async () => {
  const execute = (targetArgs, status, ok, payload) => queryLogsWithAuthFile(targetArgs, {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status,
      ok,
      async text() {
        return JSON.stringify(payload);
      },
    }),
  });

  await assert.rejects(
    execute(queryArgs(), 503, false, {
      success: false,
      message: 'private upstream body',
    }),
    { message: 'query request failed: status=503' },
  );
  await assert.rejects(
    execute(fieldsArgs(), 502, false, {
      success: false,
      code: 'ConsoleNeedLogin',
    }),
    { message: 'auth expired or invalid; run scripts/alilog auth' },
  );
  await assert.rejects(
    queryLogsWithAuthFile(queryArgs(), {
      readAuthFile: async () => ({
        cookie: 'private-cookie',
        csrf_token: 'private-csrf',
      }),
      fetchWithTimeout: async () => ({
        status: 502,
        ok: false,
        async text() {
          return '<html>private gateway response</html>';
        },
      }),
    }),
    { message: 'query request failed: status=502' },
  );

  await assert.rejects(
    execute(fieldsArgs(), 200, true, {
      success: false,
      code: 'ParameterInvalid',
      message: 'bad query apiKey=private-key',
    }),
    (error) => {
      assert.strictEqual(
        error.message,
        'fields request failed: code=ParameterInvalid message=bad query apiKey=<redacted>',
      );
      assert.doesNotMatch(error.message, /private-key/);
      return true;
    },
  );
});

test('query and fields keep valid successful empty results distinct from failures', async () => {
  const execute = (targetArgs) => queryLogsWithAuthFile(targetArgs, {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status: 200,
      ok: true,
      async text() {
        return JSON.stringify({
          success: true,
          data: {
            logs: [],
          },
        });
      },
    }),
  });

  const queryOutput = await execute(queryArgs());
  const fieldsOutput = await execute(fieldsArgs());
  assert.strictEqual(formatQueryOutput(queryOutput, queryArgs()), 'no logs');
  assert.deepStrictEqual(JSON.parse(formatFieldsOutput(fieldsOutput)), {
    sampled_logs: 0,
    count: 0,
    fields: [],
  });
});

test('query and fields require an explicit boolean success before accepting an empty result', async () => {
  const execute = (targetArgs, payload) => queryLogsWithAuthFile(targetArgs, {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status: 200,
      ok: true,
      async text() {
        return JSON.stringify(payload);
      },
    }),
  });

  for (const targetArgs of [queryArgs(), fieldsArgs()]) {
    for (const [privatePayload, expectedMessage] of [
      [{}, `invalid ${targetArgs.command} response: success must be true`],
      [
        { success: 'true', private: 'apiKey=private-key' },
        `invalid ${targetArgs.command} response: success must be true`,
      ],
      [null, `invalid ${targetArgs.command} response: response must be an object`],
      [['apiKey=private-key'], `invalid ${targetArgs.command} response: response must be an object`],
    ]) {
      await assert.rejects(
        execute(targetArgs, privatePayload),
        (error) => {
          assert.strictEqual(error.message, expectedMessage);
          assert.doesNotMatch(error.message, /private|apiKey/i);
          return true;
        },
      );
    }
  }
});

test('query failed output keeps SLS error compact', () => {
  const text = formatQueryOutput({
    response: { status: 200, ok: true },
    result: normalizeResult({
      success: false,
      code: 'ParameterInvalid',
      message: `SyntaxError ${'x '.repeat(1000)}`,
    }),
  }, args());

  assert.match(text, /^query failed: status=200 code=ParameterInvalid message=SyntaxError/);
  assert.match(text, /\[message truncated\]/);
  assert.ok(text.length < 750, `error output too long: ${text.length}`);
});

test('fields output lists field names without hits', () => {
  const text = formatFieldsOutput(output([
    { _container_name_: 'svc', content: 'hello', level: 'INFO' },
    { _container_name_: 'svc', message: 'fallback' },
  ]));
  const parsed = JSON.parse(text);

  assert.deepStrictEqual(parsed, {
    sampled_logs: 2,
    count: 4,
    fields: ['_container_name_', 'content', 'level', 'message'],
  });
});

test('fields output reports sampled logs for empty samples', () => {
  const text = formatFieldsOutput(output([]));
  const parsed = JSON.parse(text);

  assert.deepStrictEqual(parsed, {
    sampled_logs: 0,
    count: 0,
    fields: [],
  });
});

test('logstores output keeps compact pagination shape', () => {
  const text = formatLogstoresOutput({
    Count: 3,
    LogStores: [
      { LogStoreName: 'nginx-ingress' },
      { logstoreName: 'nginx-ingress-user' },
      'tomcat-log',
    ],
  }, { page: 1, pageSize: 2 });
  const parsed = JSON.parse(text);

  assert.deepStrictEqual(parsed, {
    total: 3,
    page: 1,
    page_size: 2,
    next_page: 2,
    logstores: ['nginx-ingress', 'nginx-ingress-user', 'tomcat-log'],
  });
});

test('logstores output supports console data.logStores response shape', () => {
  const text = formatLogstoresOutput({
    success: true,
    data: {
      total: 8,
      Size: 18,
      Page: 1,
      logStores: [
        { LogStoreName: 'nginx-ingress' },
        { LogStoreName: 'nginx-ingress-user' },
      ],
    },
  }, { page: 1, pageSize: 18 });
  const parsed = JSON.parse(text);

  assert.strictEqual(parsed.total, 8);
  assert.strictEqual(parsed.next_page, null);
  assert.deepStrictEqual(parsed.logstores, ['nginx-ingress', 'nginx-ingress-user']);
});

test('logstores rejects a business failure with a compact redacted error', async () => {
  await assert.rejects(
    listLogstoresWithAuthFile({
      project: 'proj',
      keyword: '',
      page: 1,
      pageSize: 18,
    }, {
      readAuthFile: async () => ({
        cookie: 'private-cookie',
        csrf_token: 'private-csrf',
      }),
      fetchWithTimeout: async () => ({
        status: 200,
        ok: true,
        async text() {
          return JSON.stringify({
            success: false,
            code: 'ProjectNotExist',
            message: 'missing api_key=private-key',
          });
        },
      }),
    }),
    (error) => {
      assert.strictEqual(
        error.message,
        'logstores request failed: code=ProjectNotExist message=missing api_key=<redacted>',
      );
      assert.doesNotMatch(error.message, /private-key|private-cookie|private-csrf/);
      return true;
    },
  );
});

test('logstores distinguishes auth, malformed, HTTP, and valid empty responses', async () => {
  const execute = (status, ok, body) => listLogstoresWithAuthFile({
    project: 'proj',
    keyword: '',
    page: 1,
    pageSize: 18,
  }, {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status,
      ok,
      async text() {
        return body;
      },
    }),
  });

  for (const invocation of [
    () => execute(401, false, '<html>private login response</html>'),
    () => execute(200, true, JSON.stringify({ success: false, code: 'ConsoleNeedLogin' })),
    () => execute(200, true, JSON.stringify({ success: false, message: 'ConsoleNeedLogin' })),
  ]) {
    await assert.rejects(invocation(), {
      message: 'auth expired or invalid; run scripts/alilog auth',
    });
  }
  await assert.rejects(execute(200, true, '<html>private body</html>'), {
    message: 'invalid logstores response: response is not valid JSON',
  });
  await assert.rejects(execute(502, false, JSON.stringify({ success: false })), {
    message: 'logstores request failed: status=502',
  });
  await assert.rejects(execute(502, false, JSON.stringify({
    success: false,
    code: 'ConsoleNeedLogin',
  })), {
    message: 'auth expired or invalid; run scripts/alilog auth',
  });
  await assert.rejects(execute(503, false, '<html>private gateway response</html>'), {
    message: 'logstores request failed: status=503',
  });

  const payload = await execute(200, true, JSON.stringify({
    success: true,
    data: {
      total: 0,
      logStores: [],
    },
  }));
  assert.deepStrictEqual(JSON.parse(formatLogstoresOutput(payload, {
    page: 1,
    pageSize: 18,
  })), {
    total: 0,
    page: 1,
    page_size: 18,
    next_page: null,
    logstores: [],
  });
});

test('logstores requires an explicit boolean success before accepting an empty result', async () => {
  const execute = (payload) => listLogstoresWithAuthFile({
    project: 'proj',
    keyword: '',
    page: 1,
    pageSize: 18,
  }, {
    readAuthFile: async () => ({
      cookie: 'private-cookie',
      csrf_token: 'private-csrf',
    }),
    fetchWithTimeout: async () => ({
      status: 200,
      ok: true,
      async text() {
        return JSON.stringify(payload);
      },
    }),
  });

  for (const [privatePayload, expectedMessage] of [
    [{}, 'invalid logstores response: success must be true'],
    [
      { success: 'true', private: 'apiKey=private-key' },
      'invalid logstores response: success must be true',
    ],
    [null, 'invalid logstores response: response must be an object'],
    [['apiKey=private-key'], 'invalid logstores response: response must be an object'],
  ]) {
    await assert.rejects(
      execute(privatePayload),
      (error) => {
        assert.strictEqual(error.message, expectedMessage);
        assert.doesNotMatch(error.message, /private|apiKey/i);
        return true;
      },
    );
  }
});

test('logstores request uses console list endpoint and compact search params', () => {
  const url = new URL(buildLogstoresRequest({
    project: 'kuebernetes-production',
    keyword: 'nginx',
    page: 2,
    pageSize: 18,
  }));

  assert.strictEqual(url.origin + url.pathname, 'https://sls.console.aliyun.com/console/logstore/list.json');
  assert.strictEqual(url.searchParams.get('IsListOnly'), '1');
  assert.strictEqual(url.searchParams.get('LogStoreName'), 'nginx');
  assert.strictEqual(url.searchParams.get('Page'), '2');
  assert.strictEqual(url.searchParams.get('Size'), '18');
  assert.strictEqual(url.searchParams.get('ProjectName'), 'kuebernetes-production');
  assert.strictEqual(url.searchParams.get('telemetryType'), 'None');
});

test('--select-fields prints only requested nested fields', () => {
  const parsed = queryArgs(['--select-fields', '_container_name_,content']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: 'hello', level: 'INFO' },
  ]), parsed);

  assert.match(text, /\[1\] time=- container=svc/);
  assert.match(text, /content: hello/);
  assert.doesNotMatch(text, /level:/);
  assert.doesNotMatch(text, /_container_name_:/);
});

test('compact output trims horizontal whitespace and collapses repeated newlines', () => {
  const text = formatQueryOutput(output([
    {
      _container_name_: 'svc',
      message: '  hello\n\n\tworld   user   id  ',
    },
  ]), args());

  assert.match(text, /message=hello\nworld user id/);
  assert.doesNotMatch(text, /\n\n|\t|  /);
});

test('compact output preserves stack trace lines', () => {
  const text = formatQueryOutput(output([
    {
      _container_name_: 'svc',
      message: [
        ' java.lang.RuntimeException: boom ',
        '   at a.b.C.method(C.java:1) ',
        '      at a.b.D.method(D.java:2) ',
      ].join('\n'),
    },
  ]), args());

  assert.match(text, /message=java\.lang\.RuntimeException: boom\nat a\.b\.C\.method\(C\.java:1\)\nat a\.b\.D\.method\(D\.java:2\)/);
  assert.doesNotMatch(text, / {2,}|\t/);
});

test('select-fields trims and collapses whitespace', () => {
  const parsed = queryArgs(['--select-fields', 'message,content']);
  const text = formatQueryOutput(output([
    {
      message: '  hello\n\nworld  ',
      content: '  raw\tcontent   value  ',
    },
  ]), parsed);

  assert.match(text, /message: hello\nworld/);
  assert.match(text, /content: raw content value/);
  assert.doesNotMatch(text, /\n\n|\t|  /);
});

test('--select-fields truncates long field values before total output truncation', () => {
  const parsed = queryArgs(['--select-fields', '__time__,_container_name_,message,content']);
  const content = `${'x'.repeat(500)}tail-should-not-print`;
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      _container_name_: 'svc',
      message: 'short message',
      content,
    },
  ]), parsed);

  assert.match(text, /\[1\]/);
  assert.match(text, /message: short message/);
  assert.match(text, new RegExp(`content: ${'x'.repeat(500)}`));
  assert.doesNotMatch(text, /tail-should-not-print/);
  assert.match(text, /\[field truncated: narrow --select-fields/);
  assert.doesNotMatch(text, /\[truncated: narrow --query\/--time/);
  assert.ok(text.length < 800, `output too long: ${text.length}`);
});

test('--select-fields keeps medium field values for explicit inspection', () => {
  const parsed = queryArgs(['--select-fields', 'message,content']);
  const mediumContent = `${'x'.repeat(260)}tail-should-print`;
  const text = formatQueryOutput(output([
    { message: 'short message', content: mediumContent },
  ]), parsed);

  assert.match(text, /message: short message/);
  assert.match(text, /tail-should-print/);
  assert.doesNotMatch(text, /\[field truncated:/);
});

test('--extra-fields appends metadata to default output', () => {
  const parsed = queryArgs(['--extra-fields', 'level,thread']);
  const text = formatQueryOutput(output([
    { __time__: '1765450000', _container_name_: 'svc', message: 'hello', level: 'WARN', thread: 'main' },
  ]), parsed);

  assert.match(text, /\[1\] time=2025-.* container=svc level=WARN thread=main/);
  assert.match(text, /hello/);
});

test('--extra-fields and container use compact display text', () => {
  const parsed = queryArgs(['--extra-fields', 'level,thread']);
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      _container_name_: ' svc\tname  ',
      message: 'hello',
      level: ' WARN  VALUE ',
      thread: ' main\tthread ',
    },
  ]), parsed);

  assert.match(text, /\[1\] time=2025-.* container=svc name level=WARN VALUE thread=main thread/);
  assert.doesNotMatch(text, /\t| {2,}/);
});

test('default output keeps time header when compact message is available', () => {
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      _container_name_: 'svc',
      content: 'indexed content should not be displayed by default',
      message: `${'a'.repeat(200)}tail`,
      level: 'ERROR',
      thread: 'main',
      tid: 'trace-1',
    },
  ]), args());

  assert.match(text, /\[1\] time=2025-.* container=svc/);
  assert.match(text, new RegExp(`message=${'a'.repeat(200)}`));
  assert.doesNotMatch(text, /tail/);
  assert.doesNotMatch(text, /indexed content should not be displayed by default/);
  assert.doesNotMatch(text, /level=ERROR|thread=main|tid=trace-1/);
  assert.match(text, /\[more: --continue 1:200\]/);
});

test('default output falls back to compact content when message is missing', () => {
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      _container_name_: 'svc',
      content: `${'b'.repeat(200)}tail`,
      level: 'INFO',
    },
  ]), args());

  assert.match(text, /\[1\] container=svc/);
  assert.doesNotMatch(text, /\[1\] time=/);
  assert.match(text, new RegExp(`content=${'b'.repeat(200)}`));
  assert.doesNotMatch(text, /tail/);
  assert.doesNotMatch(text, /level=INFO/);
});

test('alilog query output redacts production secrets and mobile numbers', () => {
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      _container_name_: 'svc',
      message: 'mobile=13812345678 token=secret-token password=plain-secret already=139****2222',
    },
  ]), args());

  assert.match(text, /138\*\*\*\*5678/);
  assert.match(text, /139\*\*\*\*2222/);
  assert.match(text, /token=<redacted>/);
  assert.match(text, /password=<redacted>/);
  assert.doesNotMatch(text, /13812345678|secret-token|plain-secret/);
});

test('alilog query output redacts API keys, TOTP seeds, and separated mobile numbers', () => {
  const text = formatQueryOutput(output([
    {
      _container_name_: 'svc',
      message: [
        'apiKey=camel-secret',
        'api_key: snake-secret',
        'totp_seed=seed-secret',
        'json={"apiKey":"json-secret","totp_seed":"json-seed"}',
        'mobile=138-1234-5678',
      ].join(' '),
    },
  ]), args());

  assert.match(text, /apiKey=<redacted>/);
  assert.match(text, /api_key: <redacted>/);
  assert.match(text, /totp_seed=<redacted>/);
  assert.match(text, /"apiKey":"<redacted>"/);
  assert.match(text, /"totp_seed":"<redacted>"/);
  assert.match(text, /138\*\*\*\*5678/);
  assert.doesNotMatch(text, /camel-secret|snake-secret|seed-secret|json-secret|json-seed|138-1234-5678/);
});

test('full query page prints compact page facts', () => {
  const parsed = queryArgs(['--page', '3', '--size', '2']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', message: 'one' },
    { _container_name_: 'svc', message: 'two' },
  ]), parsed);

  assert.match(text, /\[page=3 size=2 returned=2\]$/);
});

test('partial query page omits page facts', () => {
  const parsed = queryArgs(['--page', '3', '--size', '3']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', message: 'one' },
    { _container_name_: 'svc', message: 'two' },
  ]), parsed);

  assert.doesNotMatch(text, /\[page /);
});

test('select-fields full page keeps compact page facts', () => {
  const parsed = queryArgs(['--page', '2', '--size', '2', '--select-fields', 'message']);
  const text = formatQueryOutput(output([
    { message: 'one' },
    { message: 'two' },
  ]), parsed);

  assert.match(text, /\[page=2 size=2 returned=2\]$/);
});

test('default output summarizes infrastructure logs as compact summary fallback', () => {
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      remote_addr: '10.0.0.1',
      request_method: 'GET',
      request_uri: '/health',
      status: '200',
      upstream_status: '200',
      request_time: '0.012',
    },
  ]), args());

  assert.match(text, /\[1\] time=2025-.* container=-/);
  assert.match(text, /summary=/);
  assert.match(text, /request_method=GET/);
  assert.match(text, /request_uri=\/health/);
  assert.match(text, /status=200/);
  assert.doesNotMatch(text, /\n\n/);
});

test('default output summarizes SQL aggregation rows as compact result fallback', () => {
  const text = formatQueryOutput(output([
    {
      __time__: '1765450000',
      __source__: '',
      cnt: '20650',
    },
  ]), args());

  assert.match(text, /\[1\] time=2025-.* container=-/);
  assert.match(text, /result=cnt=20650/);
  assert.doesNotMatch(text, /message=/);
});

test('field args are normalized at query boundary', () => {
  const parsed = queryArgs([
    '--select-fields', 'content,level,content,missing',
    '--extra-fields', '_container_name_,content,message,level,level,thread',
  ]);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: 'hello', level: 'WARN', thread: 'main' },
  ]), parsed);

  assert.deepStrictEqual(parsed.selectFields, ['content', 'level', 'missing']);
  assert.deepStrictEqual(parsed.extraFields, ['content', 'level', 'thread']);
  assert.match(text, /content: hello/);
  assert.match(text, /level: WARN/);
  assert.match(text, /missing: ?$/m);
});

test('--extra-fields skips default fields and missing fields stay blank', () => {
  const parsed = queryArgs(['--extra-fields', '_container_name_,content,message,level,missing']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: 'hello', level: 'WARN' },
  ]), parsed);

  assert.match(text, /\[1\] container=svc content=hello level=WARN missing=/);
  assert.doesNotMatch(text, /\[1\] time=/);
  assert.doesNotMatch(text, /_container_name_=/);
  assert.doesNotMatch(text, /message=/);
});

test('--continue renders a long nested content fragment', () => {
  const parsed = queryArgs(['--continue', '1:1300']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: longContent },
  ]), parsed);

  assert.strictEqual(text, 'continued tail');
  assert.doesNotMatch(text, /truncated:/);
});

test('--continue follows default message body before indexed content', () => {
  const parsed = queryArgs(['--continue', '1:200']);
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', message: `${'m'.repeat(200)}continued message`, content: `${'c'.repeat(200)}indexed content` },
  ]), parsed);

  assert.strictEqual(text, 'continued message');
  assert.doesNotMatch(text, /indexed content/);
});

test('--continue slices the fully redacted body so a boundary cannot reveal a secret tail', () => {
  const secret = 'secret-token-value';
  const message = `${'x'.repeat(190)} token=${secret} visible-tail`;
  const firstPage = formatQueryOutput(output([
    { _container_name_: 'svc', message },
  ]), args());
  const continuation = formatQueryOutput(output([
    { _container_name_: 'svc', message },
  ]), queryArgs(['--continue', '1:200']));

  assert.match(firstPage, /token=<redacted>/);
  assert.doesNotMatch(`${firstPage}\n${continuation}`, /secret-token-value|ret-token-value|token-value/);
  assert.match(continuation, /visible-tail/);
  for (let offset = 0; offset <= message.length + 5; offset += 1) {
    const page = formatQueryOutput(output([
      { _container_name_: 'svc', message },
    ]), queryArgs(['--continue', `1:${offset}`]));
    for (let index = 0; index <= secret.length - 6; index += 1) {
      assert.strictEqual(page.includes(secret.slice(index)), false, `offset=${offset} secret-index=${index}`);
    }
  }
});

test('SQL folding preserves business lines and folds SQL lines', () => {
  const shortSqlContent = [
    'business before',
    '==>  Preparing: select * from users',
    '<==      Total: 1',
    'business after',
  ].join('\n');
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: shortSqlContent },
  ]), args());

  assert.match(text, /business before/);
  assert.match(text, /business after/);
  assert.match(text, /\[sql x2\]/);
  assert.doesNotMatch(text, /Preparing: select/);
  assert.doesNotMatch(text, /Updates: 1/);
});

test('SQL folding keeps original text when marker is not shorter', () => {
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: '<== Row:' },
  ]), args());

  assert.match(text, /<== Row:/);
  assert.doesNotMatch(text, /\[sql x1\]/);
});

test('SQL folding preserves error lines that mention SqlSession or JDBC Connection', () => {
  const text = formatQueryOutput(output([
    {
      _container_name_: 'svc',
      content: [
        'ERROR failed to commit SqlSession for order=42',
        'java.lang.IllegalStateException: JDBC Connection failed during checkout',
      ].join('\n'),
    },
  ]), args());

  assert.match(text, /ERROR failed to commit SqlSession for order=42/);
  assert.match(text, /IllegalStateException: JDBC Connection failed during checkout/);
  assert.doesNotMatch(text, /\[sql x/);
});

test('--expand-sql shows SQL lines instead of folded marker', () => {
  const shortSqlContent = [
    'business before',
    '==>  Preparing: select * from users',
    '<==      Updates: 1',
    'business after',
  ].join('\n');
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: shortSqlContent },
  ]), args({ expandSql: true }));

  assert.match(text, /Preparing: select \* from users/);
  assert.match(text, /Updates: 1/);
  assert.doesNotMatch(text, /\[sql x8\]/);
});

test('long content uses compact continue hint', () => {
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: longContent },
  ]), args());

  assert.match(text, /\[more: --continue 1:200\]/);
  assert.doesNotMatch(text, /truncated:/);
});

test('default body window stays at 200 chars for multi-log queries', () => {
  const shortText = formatQueryOutput(output([
    { _container_name_: 'svc', content: 'x'.repeat(200) },
    { _container_name_: 'svc', content: 'z'.repeat(200) },
  ]), args());
  const longText = formatQueryOutput(output([
    { _container_name_: 'svc', content: `${'x'.repeat(200)}y` },
    { _container_name_: 'svc', content: `${'z'.repeat(200)}w` },
  ]), args());

  assert.doesNotMatch(shortText, /more: --continue/);
  assert.match(longText, /content=x{200}\n\[more: --continue 1:200\]/);
  assert.match(longText, /content=z{200}\n\[more: --continue 2:200\]/);
  assert.doesNotMatch(longText, /y/);
  assert.doesNotMatch(longText, /w/);
});

test('--continue uses an 800 char window for one selected log body', () => {
  const body = `${'a'.repeat(200)}${'b'.repeat(800)}${'c'.repeat(5)}`;
  const text = formatQueryOutput(output([
    { _container_name_: 'svc', content: body },
  ]), queryArgs(['--continue', '1:200']));

  assert.strictEqual(text, `${'b'.repeat(800)}\n[more: --continue 1:1000]`);
  assert.doesNotMatch(text, /a/);
  assert.doesNotMatch(text, /ccccc/);
});

test('total output limit uses compact truncate hint', () => {
  const logs = Array.from({ length: 20 }, (_, index) => ({
    _container_name_: 'svc',
    content: `line-${index}-${'x'.repeat(220)}`,
  }));
  const text = formatQueryOutput(output(logs), args());

  assert.ok(text.length <= 3200, `output too long: ${text.length}`);
  assert.match(text, /\[truncated: narrow --query\/--time, use --select-fields, or paginate\]/);
  assert.doesNotMatch(text, /total limit reached/);
});

test('buildQueryBody converts explicit local datetimes and rejects digit-only --from', () => {
  const parsed = queryArgs();
  const query = buildQueryBody(parsed);
  const expectedFrom = Math.floor(new Date('2026-06-01T14:00:00').getTime() / 1000);
  const expectedTo = Math.floor(new Date('2026-06-01T14:05:00').getTime() / 1000);

  assert.strictEqual(query.scope.from, expectedFrom);
  assert.strictEqual(query.scope.to, expectedTo);
  assert.strictEqual(parseTime('2026-06-01 14:00:00', '--from'), expectedFrom);
  assert.strictEqual(parseTime('2026-06-01T14:00:00', '--from'), expectedFrom);
  assertThrowsMessage(() => queryArgs(['--from', '1717200000']), /explicit datetime/);
});

test('buildQueryBody accepts --time and rejects mixed time arguments', async () => {
  await withFakeNow(new Date('2026-06-12T14:04:13+08:00').getTime(), () => {
    const parsed = parseArgs([
      'query',
      '--project', 'proj',
      '--logstore', 'store',
      '--query', '*',
      '--time', 'last_15m',
    ]);
    const body = buildQueryBody(parsed);
    assert.strictEqual(body.scope.to - body.scope.from, 15 * 60);

    assertThrowsMessage(() => parseArgs([
      'query',
      '--project', 'proj',
      '--logstore', 'store',
      '--query', '*',
      '--time', 'last_15m',
      '--from', '2026-06-12 13:00:00',
      '--to', '2026-06-12 14:00:00',
    ]), /--time cannot be combined/);
  });
});

test('parseTimeExpression supports presets, relative windows, and keywords', async () => {
  await withFakeNow(new Date('2026-06-12T14:04:13+08:00').getTime(), () => {
    const now = Math.floor(new Date('2026-06-12T14:04:13+08:00').getTime() / 1000);
    assert.deepStrictEqual(parseTimeExpression('last_15m'), { from: now - 15 * 60, to: now });
    assert.deepStrictEqual(parseTimeExpression('now-15m~now-5m'), { from: now - 15 * 60, to: now - 5 * 60 });
    assert.deepStrictEqual(parseTimeExpression('now-1h'), { from: now - 60 * 60, to: now });
    assert.deepStrictEqual(parseTimeExpression('today'), {
      from: Math.floor(new Date('2026-06-12T00:00:00').getTime() / 1000),
      to: now,
    });
    assert.deepStrictEqual(parseTimeExpression('yesterday'), {
      from: Math.floor(new Date('2026-06-11T00:00:00').getTime() / 1000),
      to: Math.floor(new Date('2026-06-12T00:00:00').getTime() / 1000),
    });
  });
});

test('parseTime rejects loose and date-only values', () => {
  assertThrowsMessage(() => parseTime('2026-06-01', '--from'), /explicit datetime/);
  assertThrowsMessage(() => parseTime('2026/06/01', '--from'), /explicit datetime/);
  assertThrowsMessage(() => parseTime('June 1, 2026', '--from'), /explicit datetime/);
  assertThrowsMessage(() => parseTime('2026-02-31 14:00:00', '--from'), /invalid --from/);
  assert.doesNotThrow(() => parseTime('2026-06-01 14:00:00', '--from'));
  assert.doesNotThrow(() => parseTime('2026-06-01T14:00:00Z', '--from'));
  assert.doesNotThrow(() => parseTime('2026-06-01T14:00:00+08:00', '--from'));
});

test('runAliyunAutoFillMonitor corrects initial non-empty username once', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const username = fakeInput('@example.com');
    const page = fakeLoginPage({
      '#loginName': username,
    }, {
      afterWait(waitCount) {
        if (waitCount === 1) username.value = 'bob@example.com';
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 1,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(username.fills, ['alice@example.com']);
    assert.strictEqual(username.value, 'bob@example.com');
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor keeps manual username edits after same-url navigation', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const username = fakeInput('@example.com');
    const page = fakeLoginPage({
      '#loginName': username,
    }, {
      afterWait(waitCount, loginPage) {
        if (waitCount === 1) {
          username.value = 'bob@example.com';
          loginPage.setUrl('https://signin.aliyun.com/example/login.htm#/main');
        }
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 1,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(username.fills, ['alice@example.com']);
    assert.strictEqual(username.value, 'bob@example.com');
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor refills non-first empty username after 1s only', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    await withFakeNow(1000, async (advanceTime) => {
      const username = fakeInput('alice@example.com');
      const page = fakeLoginPage({
        '#loginName': username,
      }, {
        loggedInAfterWaits: 4,
        advanceTime,
        afterWait(waitCount) {
          if (waitCount === 1) username.value = '';
          if (waitCount === 2) assert.deepStrictEqual(username.fills, []);
          if (waitCount === 3) assert.deepStrictEqual(username.fills, []);
        },
      });

      await runAliyunAutoFillMonitor(page, keychainArgs({
        username: 'alice@example.com',
        timeout: 3,
        debug: false,
        totpInputSelector: '',
      }));

      assert.deepStrictEqual(username.fills, ['alice@example.com']);
      assert.strictEqual(username.value, 'alice@example.com');
      assert.deepStrictEqual(page.waitDurations, [500, 500, 500, 500]);
    });
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor keeps manual username edits after url changes', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const username = fakeInput('@example.com');
    const page = fakeLoginPage({
      '#loginName': username,
    }, {
      loggedInAfterWaits: 3,
      afterWait(waitCount, loginPage) {
        if (waitCount === 1) {
          username.value = 'bob@example.com';
          loginPage.setUrl('https://signin.aliyun.com/example/login.htm#/refresh');
        }
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 1,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(username.fills, ['alice@example.com']);
    assert.strictEqual(username.value, 'bob@example.com');
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor fills password even after user changes username', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const username = fakeInput('@example.com');
    const password = fakeInput('');
    password.visible = false;
    const page = fakeLoginPage({
      '#loginName': username,
      '#loginPassword': password,
    }, {
      afterWait(waitCount) {
        if (waitCount === 1) {
          username.value = 'bob@example.com';
          password.visible = true;
        }
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 1,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(username.fills, ['alice@example.com']);
    assert.deepStrictEqual(password.fills, ['pw']);
    assert.strictEqual(password.value, 'pw');
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor fills password when username input is not on the current page', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const password = fakeInput('');
    const page = fakeLoginPage({
      '#loginPassword': password,
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 1,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(password.fills, ['pw']);
    assert.strictEqual(password.value, 'pw');
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
  }
});

test('runAliyunAutoFillMonitor keeps password and totp empty-field fill rules with username mismatch', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  const oldTotpSeed = process.env.ALILOG_TOTP_SEED;
  process.env.ALILOG_PASSWORD = 'pw';
  process.env.ALILOG_TOTP_SEED = 'JBSWY3DPEHPK3PXP';
  try {
    await withFakeNow(31000, async (advanceTime) => {
      const username = fakeInput('bob@example.com');
      const password = fakeInput('');
      const totp = fakeInput('');
      const page = fakeLoginPage({
        '#loginName': username,
        '#loginPassword': password,
        'input[placeholder="请输入 6 位数字安全码"]': totp,
      }, {
        advanceTime,
      });

      await runAliyunAutoFillMonitor(page, keychainArgs({
        username: 'alice@example.com',
        timeout: 2,
        debug: false,
        totpInputSelector: '',
      }));

      assert.deepStrictEqual(username.fills, ['alice@example.com']);
      assert.deepStrictEqual(password.fills, ['pw']);
      assert.strictEqual(totp.fills.length, 1);
      assert.match(totp.fills[0], /^\d{6}$/);
    });
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
    if (oldTotpSeed === undefined) {
      delete process.env.ALILOG_TOTP_SEED;
    } else {
      process.env.ALILOG_TOTP_SEED = oldTotpSeed;
    }
  }
});

test('runAliyunAutoFillMonitor preserves user-entered password and totp', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  const oldTotpSeed = process.env.ALILOG_TOTP_SEED;
  process.env.ALILOG_PASSWORD = 'pw';
  process.env.ALILOG_TOTP_SEED = 'JBSWY3DPEHPK3PXP';
  try {
    await withFakeNow(23900, async (advanceTime) => {
      const password = fakeInput('user-password');
      const totp = fakeInput('123456');
      const page = fakeLoginPage({
        '#loginPassword': password,
        'input[placeholder="请输入 6 位数字安全码"]': totp,
      }, {
        loggedInAfterWaits: 2,
        advanceTime,
      });

      await runAliyunAutoFillMonitor(page, keychainArgs({
        username: 'alice@example.com',
        timeout: 2,
        debug: false,
        totpInputSelector: '',
      }));

      assert.deepStrictEqual(password.fills, []);
      assert.strictEqual(password.value, 'user-password');
      assert.deepStrictEqual(totp.fills, []);
      assert.strictEqual(totp.value, '123456');
    });
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
    if (oldTotpSeed === undefined) {
      delete process.env.ALILOG_TOTP_SEED;
    } else {
      process.env.ALILOG_TOTP_SEED = oldTotpSeed;
    }
  }
});

test('runAliyunAutoFillMonitor refreshes a script-filled totp in the next period', async () => {
  await withFakeNow(23900, async (advanceTime) => {
    const totp = fakeInput('');
    const page = fakeLoginPage({
      'input[placeholder="请输入 6 位数字安全码"]': totp,
    }, {
      advanceTime,
      loggedInAfterWaits: Number.POSITIVE_INFINITY,
      afterWait(_waitCount, loginPage) {
        if (totp.fills.length === 2) {
          loginPage.setUrl('https://sls.console.aliyun.com/lognext/project/proj/logsearch/store');
        }
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      timeout: 10,
      debug: false,
      totpInputSelector: '',
    }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
    });

    assert.strictEqual(totp.fills.length, 2);
    assert.notStrictEqual(totp.fills[0], totp.fills[1]);
    assert.deepStrictEqual(totp.fillTimes, [23900, 31400]);
  });
});

test('runAliyunAutoFillMonitor does not fill local totp into phone code input', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  const oldTotpSeed = process.env.ALILOG_TOTP_SEED;
  process.env.ALILOG_PASSWORD = 'pw';
  process.env.ALILOG_TOTP_SEED = 'JBSWY3DPEHPK3PXP';
  try {
    await withFakeNow(31000, async (advanceTime) => {
      const username = fakeInput('alice@example.com');
      const password = fakeInput('');
      const phoneCode = fakeInput('');
      const page = fakeLoginPage({
        '#loginName': username,
        '#loginPassword': password,
        '#PHONE_CODE': phoneCode,
        'input[placeholder="请输入 6 位数字验证码"]': phoneCode,
      }, {
        advanceTime,
      });

      await runAliyunAutoFillMonitor(page, keychainArgs({
        username: 'alice@example.com',
        timeout: 2,
        debug: false,
        totpInputSelector: '',
      }));

      assert.deepStrictEqual(phoneCode.fills, []);
      assert.deepStrictEqual(page.injectedNotices.at(-1), [
        '登录辅助已就绪',
        '账号、密码、安全码会在输入框为空时自动填充；手机验证码请手动获取并填写',
        '按钮需要你点击；你自己填写时，脚本不会拦截或覆盖。',
        '自动填充配置见 references/first-use.md。',
      ].join('\n'));
    });
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
    if (oldTotpSeed === undefined) {
      delete process.env.ALILOG_TOTP_SEED;
    } else {
      process.env.ALILOG_TOTP_SEED = oldTotpSeed;
    }
  }
});

test('runAliyunAutoFillMonitor does not fill local totp into ambiguous otp field', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  const oldTotpSeed = process.env.ALILOG_TOTP_SEED;
  process.env.ALILOG_PASSWORD = 'pw';
  process.env.ALILOG_TOTP_SEED = 'JBSWY3DPEHPK3PXP';
  try {
    await withFakeNow(31000, async (advanceTime) => {
      const username = fakeInput('alice@example.com');
      const password = fakeInput('');
      const ambiguousOtp = fakeInput('');
      const page = fakeLoginPage({
        '#loginName': username,
        '#loginPassword': password,
        'input[name="otp"]': ambiguousOtp,
      }, {
        advanceTime,
      });

      await runAliyunAutoFillMonitor(page, keychainArgs({
        username: 'alice@example.com',
        timeout: 2,
        debug: false,
        totpInputSelector: '',
      }));

      assert.deepStrictEqual(ambiguousOtp.fills, []);
    });
  } finally {
    if (oldPassword === undefined) {
      delete process.env.ALILOG_PASSWORD;
    } else {
      process.env.ALILOG_PASSWORD = oldPassword;
    }
    if (oldTotpSeed === undefined) {
      delete process.env.ALILOG_TOTP_SEED;
    } else {
      process.env.ALILOG_TOTP_SEED = oldTotpSeed;
    }
  }
});

test('runAliyunAutoFillMonitor waits one tick when captcha is followed by password rejection', async () => {
  const username = fakeInput('');
  const password = fakeInput('');
  const page = fakeLoginPage({
    '#loginName': username,
    '#loginPassword': password,
  }, {
    loggedInAfterWaits: 99,
    frames(waitCount) {
      return [fakeCaptchaFrame(waitCount === 0
        ? { '#nocaptcha.nc-container': captchaElement() }
        : { '[role="alert"].next-message-error': captchaElement({ textContent: '用户名或密码错误' }) })];
    },
  });

  await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 3 }), {
    autoFillPlan: { username: 'alice@example.com', password: 'saved-password', totpSeed: null },
  });

  assert.deepStrictEqual(page.waitDurations, [500]);
  assert.deepStrictEqual(page.gotoUrls, []);
  assert.deepStrictEqual(username.fills, []);
  assert.deepStrictEqual(password.fills, []);
  assert.match(page.injectedNotices.at(-1), /账号或密码错误/);
});

test('runAliyunAutoFillMonitor resumes normal fill when a one-tick captcha disappears', async () => {
  const username = fakeInput('');
  const page = fakeLoginPage({ '#loginName': username }, {
    loggedInAfterWaits: 2,
    frames(waitCount) {
      return [fakeCaptchaFrame(waitCount === 0
        ? { '#nocaptcha.nc-container': captchaElement() }
        : {})];
    },
  });

  await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 3 }), {
    autoFillPlan: { username: 'alice@example.com', password: null, totpSeed: null },
  });

  assert.deepStrictEqual(page.gotoUrls, []);
  assert.deepStrictEqual(username.fills, ['alice@example.com']);
  assert.deepStrictEqual(page.waitDurations, [500, 500]);
});

test('runAliyunAutoFillMonitor stops immediately on password rejection and hands the current page to the user', async () => {
  const username = fakeInput('');
  const password = fakeInput('');
  const page = fakeLoginPage({
    '#loginName': username,
    '#loginPassword': password,
  }, {
    loggedInAfterWaits: 99,
    frames() {
      return [fakeCaptchaFrame({
        '[role="alert"].next-message-error': captchaElement({
          textContent: '用户名或密码错误，还可以重试3次 RequestId：private-request-id',
        }),
      })];
    },
  });

  await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 3 }), {
    autoFillPlan: { username: 'alice@example.com', password: 'saved-password', totpSeed: null },
  });

  assert.deepStrictEqual(username.fills, []);
  assert.deepStrictEqual(password.fills, []);
  assert.deepStrictEqual(page.gotoUrls, []);
  assert.deepStrictEqual(page.waitDurations, []);
  const guidance = page.injectedNotices.at(-1);
  assert.strictEqual(guidance, [
    '账号或密码错误，自动填充已停止。请选择一种处理方式：',
    '',
    '1. 手动登录：在当前窗口完成登录。',
    '2. 修正自动登录：关闭当前窗口，检查账号并更新 Keychain 密码，然后重新运行 scripts/alilog auth。',
  ].join('\n'));
  assert.doesNotMatch(guidance, /继续|自行选择|手动输入(?:正确)?(?:密码|安全码)/);
  assert.ok(guidance.indexOf('关闭当前窗口') < guidance.indexOf('更新 Keychain 密码'));
  assert.ok(guidance.indexOf('更新 Keychain 密码') < guidance.indexOf('重新运行 scripts/alilog auth'));
});

test('runAliyunAutoFillMonitor stops immediately on TOTP rejection without clearing or refilling the code', async () => {
  const totp = fakeInput('123456');
  const page = fakeLoginPage({
    'input[placeholder="请输入 6 位数字安全码"]': totp,
  }, {
    loggedInAfterWaits: 99,
    frames() {
      return [fakeCaptchaFrame({
        '[role="alert"].next-message-error': captchaElement({ textContent: '安全码错误。查看原因' }),
      })];
    },
  });

  await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 3 }), {
    autoFillPlan: { username: 'alice@example.com', password: 'saved-password', totpSeed: 'JBSWY3DPEHPK3PXP' },
  });

  assert.strictEqual(totp.value, '123456');
  assert.deepStrictEqual(totp.fills, []);
  assert.deepStrictEqual(page.gotoUrls, []);
  assert.deepStrictEqual(page.waitDurations, []);
  const guidance = page.injectedNotices.at(-1);
  assert.strictEqual(guidance, [
    '安全码错误，自动填充已停止；保存的 TOTP seed 可能不正确。请选择一种处理方式：',
    '',
    '1. 手动登录：在当前窗口完成登录。',
    '2. 修正自动登录：关闭当前窗口，更新 alilog-totp 中的 TOTP seed，然后重新运行 scripts/alilog auth。',
  ].join('\n'));
  assert.doesNotMatch(guidance, /继续|自行选择|手动输入(?:正确)?(?:密码|安全码)/);
  assert.ok(guidance.indexOf('关闭当前窗口') < guidance.indexOf('更新 alilog-totp 中的 TOTP seed'));
  assert.ok(guidance.indexOf('更新 alilog-totp 中的 TOTP seed') < guidance.indexOf('重新运行 scripts/alilog auth'));
});

test('hard feedback guidance navigation race reports foreign once and treats SLS as success', async () => {
  for (const [targetUrl, injectionThrows, expectedNotices] of [
    ['https://example.com/login', true, [foreignOriginHandoffNotice]],
    ['https://sls.console.aliyun.com/lognext/project/proj/logsearch/store', true, []],
    ['https://example.com/login', false, [foreignOriginHandoffNotice]],
    ['https://sls.console.aliyun.com/lognext/project/proj/logsearch/store', false, []],
  ]) {
    let injectionAttempts = 0;
    const notices = [];
    const page = fakeLoginPage({}, {
      loggedInAfterWaits: Number.POSITIVE_INFINITY,
      frames() {
        return [fakeCaptchaFrame({
          '[role="alert"].next-message-error': captchaElement({
            textContent: '用户名或密码错误，还可以重试3次',
          }),
        })];
      },
      evaluate(pageFunction, arg, loginPage) {
        if (!String(pageFunction).includes('alilog-login-guidance-notice')) return false;
        injectionAttempts += 1;
        loginPage.setUrl(targetUrl);
        if (injectionThrows) throw new Error('Execution context was destroyed during navigation');
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 3 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: null,
      },
      reportNotice: async (message) => notices.push(message),
    });

    assert.strictEqual(page.url(), targetUrl);
    assert.strictEqual(injectionAttempts, 1);
    assert.deepStrictEqual(page.injectedNotices, []);
    assert.deepStrictEqual(notices, expectedNotices);
    assert.deepStrictEqual(page.waitDurations, []);
  }
});

test('runAliyunAutoFillMonitor shares two recovery attempts across captcha and unknown visible errors', async () => {
  const page = fakeLoginPage({}, {
    loggedInAfterWaits: 99,
    frames() {
      const recoveryCount = page.gotoUrls.filter((url) => url === 'about:blank').length;
      if (recoveryCount === 0) {
        return [fakeCaptchaFrame({ '#nocaptcha.nc-container': captchaElement() })];
      }
      if (recoveryCount === 1) {
        return [fakeCaptchaFrame({
          '[role="alert"].next-message-error': captchaElement({ textContent: '当前登录状态无法继续，请稍后再试' }),
        })];
      }
      return [fakeCaptchaFrame({ '#nocaptcha.nc-container': captchaElement() })];
    },
  });

  await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 5 }), {
    autoFillPlan: { username: '', password: null, totpSeed: null },
  });

  assert.deepStrictEqual(page.gotoUrls.filter((url) => url === 'about:blank'), ['about:blank', 'about:blank']);
  assert.deepStrictEqual(page.waitDurations, [500, 500, 500]);
  assert.match(page.injectedNotices.at(-1), /自动恢复已尝试 2 次仍失败/);
});

test('runAliyunAutoFillMonitor restarts login flow immediately on captcha without filling fields', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const username = fakeInput('');
    const password = fakeInput('');
    const page = fakeLoginPage({
      '#loginName': username,
      '#loginPassword': password,
    }, {
      loggedInAfterWaits: 4,
      advanceTime,
      frames() {
        return [
          fakeCaptchaFrame({
            '#nocaptcha .nc_wrapper': captchaElement({ textContent: '验证失败，点击框体重试(error:83S1w5)' }),
          }),
        ];
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: 'alice@example.com',
      timeout: 3,
      debug: false,
      totpInputSelector: '',
    }));

    assert.strictEqual(page.gotoUrls.length, 4);
    assert.strictEqual(page.gotoUrls[0], 'about:blank');
    assert.match(page.gotoUrls[1], /^https:\/\/signin\.aliyun\.com\//);
    assert.deepStrictEqual(username.fills, []);
    assert.deepStrictEqual(password.fills, []);
  });
});

test('runAliyunAutoFillMonitor hides external captcha restart failures in debug output', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const restartFailure = new Error('opaque-cookie=session RequestId: abc private=value');
    restartFailure.name = 'TimeoutError';
    const page = fakeLoginPage({}, {
      advanceTime,
      frames() {
        return [
          fakeCaptchaFrame({
            '#nocaptcha .nc_wrapper': captchaElement({ textContent: '验证失败，点击框体重试(error:83S1w5)' }),
          }),
        ];
      },
      async goto() {
        throw restartFailure;
      },
    });

    const debugLogs = await captureConsoleLogs(() => runAliyunAutoFillMonitor(page, keychainArgs({
      username: '',
      timeout: 3,
      debug: true,
      totpInputSelector: '',
    })));

    const output = debugLogs.join('\n');
    assert.match(output, /login flow restart failed: TimeoutError/);
    assert.doesNotMatch(output, /opaque-cookie|RequestId|private=value/i);
  });
});

test('runAliyunAutoFillMonitor does not inject guidance on non-login blank page', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeLoginPage({}, {
      url: 'about:blank',
      loggedInAfterWaits: 2,
      advanceTime,
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: '',
      timeout: 4,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(page.injectedNotices, []);
  });
});

test('runAliyunAutoFillMonitor hands over to manual login when captcha restart leaves the browser blank', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeLoginPage({}, {
      loggedInAfterWaits: 99,
      advanceTime,
      frames(waitCount, loginPage, currentUrl) {
        return [
          fakeCaptchaFrame(() => ({
            '#nocaptcha .nc_wrapper': currentUrl === 'about:blank'
              ? null
              : captchaElement({ textContent: '验证失败，点击框体重试(error:83S1w5)' }),
          })),
        ];
      },
      async goto(url, loginPage) {
        loginPage.gotoUrls.push(url);
        if (url !== 'about:blank') throw new Error('navigation failed');
        loginPage.setUrl(url);
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: '',
      timeout: 3,
      debug: false,
      totpInputSelector: '',
    }));

    assert.strictEqual(page.gotoUrls.length, 2);
    assert.strictEqual(page.gotoUrls[0], 'about:blank');
    assert.match(page.gotoUrls[1], /^https:\/\/signin\.aliyun\.com\//);
    assert.deepStrictEqual(page.injectedNotices, []);
  });
});

test('runAliyunAutoFillMonitor stops auto-fill and shows guidance notice after captcha limit', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const username = fakeInput('');
    const page = fakeLoginPage({
      '#loginName': username,
    }, {
      loggedInAfterWaits: 99,
      advanceTime,
      frames() {
        return [
          fakeCaptchaFrame({
            '#nocaptcha .nc_wrapper': captchaElement({ textContent: '验证失败，点击框体重试(error:83S1w5)' }),
          }),
        ];
      },
    });

    await runAliyunAutoFillMonitor(page, keychainArgs({
      username: '',
      timeout: 5,
      debug: false,
      totpInputSelector: '',
    }));

    assert.strictEqual(page.gotoUrls.length, 4);
    assert.deepStrictEqual(page.gotoUrls.filter((url) => url === 'about:blank'), ['about:blank', 'about:blank']);
    assert.strictEqual(page.injectedNotices.length > 0, true);
    assert.strictEqual(page.injectedNotices.at(-1), [
      '检测到阿里云滑块验证，自动恢复已尝试 2 次仍失败。',
      '已停止自动填充，请完整手动登录。',
      '登录成功后脚本会继续保存 SLS 登录态；不要关闭此窗口。',
    ].join('\n'));
    assert.match(page.injectedNoticeSources.at(-1), /translateX\(-50%\)/);
    assert.match(page.injectedNoticeSources.at(-1), /paddingTop/);
    assert.match(page.injectedNoticeSources.at(-1), /padding = '13px 14px'/);
    assert.match(page.injectedNoticeSources.at(-1), /border = '1px solid #f59e0b'/);
    assert.match(page.injectedNoticeSources.at(-1), /borderLeft = '4px solid #ea580c'/);
    assert.match(page.injectedNoticeSources.at(-1), /fontSize = '15px'/);
    assert.match(page.injectedNoticeSources.at(-1), /lineHeight = '22px'/);
    assert.match(page.injectedNoticeSources.at(-1), /fontWeight = '600'/);
    assert.match(page.injectedNoticeSources.at(-1), /whiteSpace = 'pre-line'/);
    assert.doesNotMatch(page.injectedNoticeSources.at(-1), /fontSize = '17px'|fontWeight = '750'|border = '2px/);
    assert.doesNotMatch(page.injectedNoticeSources.at(-1), /translate\(-50%, -50%\)/);
  });
});

test('openLoginPage classifies signin navigation failure without exposing browser details', async () => {
  const page = {
    async goto() {
      const error = new Error('opaque token=unstructured-secret RequestId: abc cookie=session');
      error.name = 'TimeoutError';
      throw error;
    },
  };

  await assert.rejects(
    () => openLoginPage(page, {}, keychainArgs()),
    (error) => {
      assert.strictEqual(error.message, 'failed to open Aliyun login page: TimeoutError');
      assert.doesNotMatch(error.message, /opaque|unstructured-secret|RequestId|cookie/i);
      return true;
    },
  );
});

test('reportAutoFillFailure only prints a safe external error type in auth debug mode', () => {
  const lines = [];
  const originalLog = console.log;
  console.log = (line) => lines.push(String(line));
  try {
    const externalFailure = new Error('opaque-private-value=unstructured-secret RequestId: abc cookie=session');
    externalFailure.name = 'TimeoutError';

    reportAutoFillFailure({ debug: false }, externalFailure);
    assert.deepStrictEqual(lines, []);

    reportAutoFillFailure({ debug: true }, externalFailure);
    assert.match(lines[0], /^auth: auto-fill failed: TimeoutError \d{2}:\d{2}:\d{2}\.\d{3}$/);
    assert.doesNotMatch(lines.join('\n'), /opaque-private-value|unstructured-secret|RequestId|cookie/i);
  } finally {
    console.log = originalLog;
  }
});

test('runAliyunAutoFillMonitor reports unsupported TOTP only through debug', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  const oldSeed = process.env.ALILOG_TOTP_SEED;
  const lines = [];
  const originalLog = console.log;
  process.env.ALILOG_PASSWORD = 'password';
  process.env.ALILOG_TOTP_SEED = 'otpauth://totp/Aliyun?secret=JBSWY3DPEHPK3PXP&algorithm=SHA256';
  console.log = (line) => lines.push(String(line));
  try {
    await runAliyunAutoFillMonitor(fakeLoginPage({}, { loggedInAfterWaits: 1 }), keychainArgs({
      username: 'user@example.com',
      timeout: 1,
      debug: true,
    }));
    assert.ok(lines.some((line) => /^auth: TOTP configuration unsupported; treating as unavailable \d{2}:\d{2}:\d{2}\.\d{3}$/.test(line)));
  } finally {
    console.log = originalLog;
    if (oldPassword === undefined) delete process.env.ALILOG_PASSWORD;
    else process.env.ALILOG_PASSWORD = oldPassword;
    if (oldSeed === undefined) delete process.env.ALILOG_TOTP_SEED;
    else process.env.ALILOG_TOTP_SEED = oldSeed;
  }
});

test('fetchWithTimeout aborts slow query fetch with clear error', async () => {
  const neverFetch = (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      const error = new Error('aborted');
      error.name = 'AbortError';
      reject(error);
    });
  });

  await assert.rejects(
    fetchWithTimeout('https://sls.console.aliyun.com/console/logstoreindex/getLogs.json', {}, 5, neverFetch),
    /SLS query request timed out after 1s/,
  );
});

test('fetchWithTimeout combines caller signal and cleans listener', async () => {
  const caller = new AbortController();
  const originalAddEventListener = caller.signal.addEventListener.bind(caller.signal);
  const originalRemoveEventListener = caller.signal.removeEventListener.bind(caller.signal);
  let added = 0;
  let removed = 0;
  caller.signal.addEventListener = (type, listener, options) => {
    if (type === 'abort') added += 1;
    return originalAddEventListener(type, listener, options);
  };
  caller.signal.removeEventListener = (type, listener, options) => {
    if (type === 'abort') removed += 1;
    return originalRemoveEventListener(type, listener, options);
  };

  const waitingFetch = (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      const error = new Error('caller aborted');
      error.name = 'AbortError';
      reject(error);
    });
    setTimeout(() => caller.abort(), 0);
  });

  await assert.rejects(
    fetchWithTimeout('https://sls.console.aliyun.com/console/logstoreindex/getLogs.json', {
      signal: caller.signal,
    }, 5000, waitingFetch),
    (error) => error.name === 'AbortError' && /caller aborted/.test(error.message),
  );
  assert.strictEqual(added, 1);
  assert.strictEqual(removed, 1);
});

test('fetchWithTimeout passes caller abort reason to fetch signal', async () => {
  const caller = new AbortController();
  const reason = new Error('manual stop');
  let fetchSignalReason;
  const waitingFetch = (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      fetchSignalReason = options.signal.reason;
      const error = new Error('caller aborted');
      error.name = 'AbortError';
      reject(error);
    });
    setTimeout(() => caller.abort(reason), 0);
  });

  await assert.rejects(
    fetchWithTimeout('https://sls.console.aliyun.com/console/logstoreindex/getLogs.json', {
      signal: caller.signal,
    }, 5000, waitingFetch),
    (error) => error.name === 'AbortError' && /caller aborted/.test(error.message),
  );
  assert.strictEqual(fetchSignalReason, reason);
});

test('Playwright resolution returns the skill-local package without scanning npx caches', async () => {
  let readdirCalls = 0;
  const modulePath = await findPlaywrightModulePath({
    localPackage: '/skill/node_modules/playwright/package.json',
    npxRoot: '/home/.npm/_npx',
    fileSystem: {
      async stat(target) {
        assert.strictEqual(target, '/skill/node_modules/playwright/package.json');
        return { mtimeMs: 1 };
      },
      async readdir() {
        readdirCalls += 1;
        return [];
      },
    },
  });

  assert.strictEqual(modulePath, '/skill/node_modules/playwright');
  assert.strictEqual(readdirCalls, 0);
});

test('Playwright resolution uses the newest npx fallback only when the local package is absent', async () => {
  const requested = [];
  const modulePath = await findPlaywrightModulePath({
    localPackage: '/skill/node_modules/playwright/package.json',
    npxRoot: '/home/.npm/_npx',
    fileSystem: {
      async stat(target) {
        requested.push(target);
        if (target === '/skill/node_modules/playwright/package.json') {
          throw new Error('missing');
        }
        return {
          mtimeMs: target.includes('/newer/') ? 20 : 10,
        };
      },
      async readdir(target) {
        assert.strictEqual(target, '/home/.npm/_npx');
        return [
          { name: 'older', isDirectory: () => true },
          { name: 'ignored', isDirectory: () => false },
          { name: 'newer', isDirectory: () => true },
        ];
      },
    },
  });

  assert.strictEqual(modulePath, '/home/.npm/_npx/newer/node_modules/playwright');
  assert.deepStrictEqual(requested, [
    '/skill/node_modules/playwright/package.json',
    '/home/.npm/_npx/older/node_modules/playwright/package.json',
    '/home/.npm/_npx/newer/node_modules/playwright/package.json',
  ]);

  await assert.rejects(
    findPlaywrightModulePath({
      localPackage: '/skill/node_modules/playwright/package.json',
      npxRoot: '/home/.npm/_npx',
      fileSystem: {
        async stat() {
          throw new Error('missing');
        },
        async readdir() {
          return [];
        },
      },
    }),
    /Playwright library package not found/,
  );
});

test('captureSlsAuth rejects when auth file write fails', async () => {
  const page = new EventEmitter();
  const response = {
    url: () => 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
    ok: () => true,
    json: async () => ({ success: true }),
    request: () => ({
      headers: () => ({ 'x-csrf-token': 'csrf-token' }),
    }),
  };
  const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
    writeAuth: async () => {
      throw new Error('write failed');
    },
  });

  page.emit('response', response);

  await assert.rejects(authCaptured, /write failed/);
  assert.strictEqual(page.listenerCount('response'), 0);
  assert.strictEqual(page.listenerCount('framenavigated'), 0);
});

test('auth persistence keeps the previous file and removes its temporary file when rename fails', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'alilog-auth-atomic-'));
  const authFile = path.join(directory, 'auth.json');
  fs.writeFileSync(authFile, '{"old":true}\n', 'utf8');
  try {
    await assert.rejects(
      writeAuthFile({
        authFile,
        project: 'proj',
        logstore: 'store',
      }, {}, {
        cookies: async () => [{ name: 'session', value: 'private-cookie' }],
      }, 'private-csrf', {
        fileSystem: {
          mkdir: fsPromises.mkdir,
          open: fsPromises.open,
          rename: async () => {
            throw new Error('rename failed');
          },
          rm: fsPromises.rm,
        },
      }),
      /rename failed/,
    );

    assert.strictEqual(fs.readFileSync(authFile, 'utf8'), '{"old":true}\n');
    assert.deepStrictEqual(fs.readdirSync(directory), ['auth.json']);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('auth persistence applies mode 0600 before writing credentials', async () => {
  const events = [];
  await writeAuthFile({
    authFile: '/private/auth.json',
    project: 'proj',
    logstore: 'store',
  }, {}, {
    cookies: async () => [{ name: 'session', value: 'private-cookie' }],
  }, 'private-csrf', {
    randomUUID: () => 'fixed',
    fileSystem: {
      async mkdir() {
        events.push('mkdir');
      },
      async open(target, flags, mode) {
        events.push(['open', target, flags, mode]);
        return {
          async chmod(nextMode) {
            events.push(['chmod', nextMode]);
          },
          async writeFile(value, encoding) {
            assert.match(value, /private-cookie/);
            events.push(['write', encoding]);
          },
          async close() {
            events.push('close');
          },
        };
      },
      async rename(source, target) {
        events.push(['rename', source, target]);
      },
      async rm() {
        throw new Error('cleanup must not run');
      },
    },
  });

  assert.deepStrictEqual(events, [
    'mkdir',
    ['open', `/private/.auth.json.${process.pid}.fixed.tmp`, 'wx', 0o600],
    ['chmod', 0o600],
    ['write', 'utf8'],
    'close',
    ['rename', `/private/.auth.json.${process.pid}.fixed.tmp`, '/private/auth.json'],
  ]);
});

test('auth persistence preserves the old file after permission, write, or close failure', async () => {
  for (const failureStage of ['chmod', 'writeFile', 'close']) {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), `alilog-auth-${failureStage}-`));
    const authFile = path.join(directory, 'auth.json');
    fs.writeFileSync(authFile, '{"old":true}\n', 'utf8');
    try {
      await assert.rejects(
        writeAuthFile({
          authFile,
          project: 'proj',
          logstore: 'store',
        }, {}, {
          cookies: async () => [{ name: 'session', value: 'private-cookie' }],
        }, 'private-csrf', {
          fileSystem: {
            mkdir: fsPromises.mkdir,
            async open(...openArgs) {
              const handle = await fsPromises.open(...openArgs);
              return {
                async chmod(mode) {
                  if (failureStage === 'chmod') throw new Error('chmod failed');
                  return handle.chmod(mode);
                },
                async writeFile(value, encoding) {
                  if (failureStage === 'writeFile') throw new Error('write failed');
                  return handle.writeFile(value, encoding);
                },
                async close() {
                  await handle.close().catch(() => {});
                  if (failureStage === 'close') throw new Error('close failed');
                },
              };
            },
            rename: fsPromises.rename,
            rm: fsPromises.rm,
          },
        }),
        new RegExp(`${failureStage === 'writeFile' ? 'write' : failureStage} failed`),
      );

      assert.strictEqual(fs.readFileSync(authFile, 'utf8'), '{"old":true}\n');
      assert.deepStrictEqual(fs.readdirSync(directory), ['auth.json']);
    } finally {
      fs.rmSync(directory, { recursive: true, force: true });
    }
  }
});

test('concurrent auth writers leave one complete parseable mode-0600 file', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'alilog-auth-concurrent-'));
  const authFile = path.join(directory, 'auth.json');
  try {
    const write = (name, csrfToken) => writeAuthFile({
      authFile,
      project: 'proj',
      logstore: 'store',
    }, {}, {
      cookies: async () => [{ name: 'session', value: name }],
    }, csrfToken);

    await Promise.all([
      write('cookie-a', 'csrf-a'),
      write('cookie-b', 'csrf-b'),
    ]);

    const persisted = JSON.parse(fs.readFileSync(authFile, 'utf8'));
    assert.ok([
      'session=cookie-a|csrf-a',
      'session=cookie-b|csrf-b',
    ].includes(`${persisted.cookie}|${persisted.csrf_token}`));
    assert.strictEqual(fs.statSync(authFile).mode & 0o777, 0o600);
    assert.deepStrictEqual(fs.readdirSync(directory), ['auth.json']);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('captureSlsAuth rejects and cleans listeners when response inspection throws', async () => {
  for (const [operation, applyFailure] of [
    ['url', (response, error) => { response.url = () => { throw error; }; }],
    ['ok', (response, error) => { response.ok = () => { throw error; }; }],
    ['json', (response, error) => { response.json = async () => { throw error; }; }],
    ['request', (response, error) => { response.request = () => { throw error; }; }],
    ['headers', (response, error) => { response.request = () => ({ headers: () => { throw error; } }); }],
  ]) {
    const page = new EventEmitter();
    const error = new Error(`${operation} failed`);
    const response = {
      url: () => 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
      ok: () => true,
      json: async () => ({ success: true }),
      request: () => ({ headers: () => ({ 'x-csrf-token': 'csrf-token' }) }),
    };
    applyFailure(response, error);
    const authCaptured = captureSlsAuth(page, {}, { timeout: 1 });

    page.emit('response', response);

    await assert.rejects(authCaptured, (capturedError) => capturedError === error);
    assert.strictEqual(page.listenerCount('response'), 0);
    assert.strictEqual(page.listenerCount('framenavigated'), 0);
  }
});

test('captureSlsAuth writes auth after successful getLogs responses', async () => {
  for (const responsePath of [
    '/console/logstoreindex/getLogs.json',
    '/console/logs/getLogs.json',
  ]) {
    const page = new EventEmitter();
    const calls = [];
    const response = {
      url: () => `https://sls.console.aliyun.com${responsePath}`,
      ok: () => true,
      json: async () => ({ success: true }),
      request: () => ({
        headers: () => ({ 'x-csrf-token': `csrf-for-${responsePath}` }),
      }),
    };
    const authCaptured = captureSlsAuth(page, { marker: 'context' }, { timeout: 1, debug: false }, {
      writeAuth: async (argsValue, pageValue, contextValue, csrfToken) => {
        calls.push({ argsValue, pageValue, contextValue, csrfToken });
      },
    });

    page.emit('response', response);
    await authCaptured;

    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].pageValue, page);
    assert.deepStrictEqual(calls[0].contextValue, { marker: 'context' });
    assert.strictEqual(calls[0].csrfToken, `csrf-for-${responsePath}`);
  }
});

test('captureSlsAuth rejects noncanonical or incomplete getLogs responses', async () => {
  for (const response of [
    {
      url: 'https://example.com/console/logstoreindex/getLogs.json',
      payload: { success: true },
    },
    {
      url: 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json/extra',
      payload: { success: true },
    },
    {
      url: 'https://sls.console.aliyun.com.evil.example/console/logstoreindex/getLogs.json',
      payload: { success: true },
    },
    {
      url: 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
      payload: {},
    },
    {
      url: 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
      payload: { success: 'true' },
    },
  ]) {
    const page = new EventEmitter();
    const abortController = new AbortController();
    let writeCount = 0;
    const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
      abortSignal: abortController.signal,
      writeAuth: async () => { writeCount += 1; },
    });

    page.emit('response', {
      url: () => response.url,
      ok: () => true,
      json: async () => response.payload,
      request: () => ({ headers: () => ({ 'x-csrf-token': 'csrf-token' }) }),
    });
    await Promise.resolve();

    assert.equal(writeCount, 0);
    abortController.abort(new Error('test stop'));
    await assert.rejects(authCaptured, /test stop/);
  }
});

test('captureSlsAuth debug reports after auth file persistence', async () => {
  const page = new EventEmitter();
  const logs = await captureConsoleLogs(async () => {
    const authCaptured = captureSlsAuth(page, {}, { timeout: 1, debug: true }, {
      writeAuth: async () => {},
    });
    page.emit('response', {
      url: () => 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
      ok: () => true,
      json: async () => ({ success: true }),
      request: () => ({ headers: () => ({ 'x-csrf-token': 'csrf-token' }) }),
    });
    await authCaptured;
  });

  assert.ok(logs.some((line) => /^auth: csrf captured \(logstoreindex\) \d{2}:\d{2}:\d{2}\.\d{3}$/.test(line)));
  assert.ok(logs.some((line) => /^auth: auth file written \d{2}:\d{2}:\d{2}\.\d{3}$/.test(line)));
});

test('captureSlsAuth writes auth once when valid responses arrive concurrently', async () => {
  const page = new EventEmitter();
  let writeCount = 0;
  let startWrite;
  let finishWrite;
  const writeStarted = new Promise((resolve) => { startWrite = resolve; });
  const allowWriteToFinish = new Promise((resolve) => { finishWrite = resolve; });
  const response = (csrfToken) => ({
    url: () => 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
    ok: () => true,
    json: async () => ({ success: true }),
    request: () => ({ headers: () => ({ 'x-csrf-token': csrfToken }) }),
  });
  const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
    writeAuth: async () => {
      writeCount += 1;
      startWrite();
      await allowWriteToFinish;
    },
  });

  page.emit('response', response('first-csrf-token'));
  await writeStarted;
  let settled = false;
  authCaptured.then(() => { settled = true; });
  await Promise.resolve();
  assert.equal(settled, false);
  page.emit('response', response('second-csrf-token'));
  finishWrite();

  await authCaptured;
  assert.equal(writeCount, 1);
  assert.equal(page.listenerCount('response'), 0);
  assert.equal(page.listenerCount('framenavigated'), 0);
});

test('captureSlsAuth does not time out after a valid getLogs response starts auth persistence', async () => {
  const page = new EventEmitter();
  page.url = () => 'https://sls.console.aliyun.com/lognext/project/project/logsearch/logstore';
  let startWrite;
  let finishWrite;
  const writeStarted = new Promise((resolve) => { startWrite = resolve; });
  const allowWriteToFinish = new Promise((resolve) => { finishWrite = resolve; });
  const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
    browserMode: 'headless',
    consoleQueryTimeoutMs: 1,
    writeAuth: async () => {
      startWrite();
      await allowWriteToFinish;
    },
  });

  page.emit('response', {
    url: () => 'https://sls.console.aliyun.com/console/logstoreindex/getLogs.json',
    ok: () => true,
    json: async () => ({ success: true }),
    request: () => ({ headers: () => ({ 'x-csrf-token': 'csrf-token' }) }),
  });
  await writeStarted;

  let state;
  try {
    state = await Promise.race([
      authCaptured.then(() => 'resolved', () => 'rejected'),
      new Promise((resolve) => setTimeout(() => resolve('pending'), 20)),
    ]);
    assert.strictEqual(state, 'pending');
  } finally {
    finishWrite();
  }
  await authCaptured;
});

test('runAuth waits for auth capture before writing success output or closing Chrome', async () => {
  const browser = { name: 'headed' };
  const events = [];
  let finishCapture;
  let startCapture;
  const captureStarted = new Promise((resolve) => { startCapture = resolve; });
  const captureFinished = new Promise((resolve) => { finishCapture = resolve; });

  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => browser,
    captureAuthWithBrowser: async () => {
      startCapture();
      await captureFinished;
    },
    writeStdoutLine: async (line) => events.push(`output:${line}`),
    disposeBrowserSession: async () => events.push('close'),
  });

  await captureStarted;
  assert.deepStrictEqual(events, []);
  finishCapture();
  await auth;

  assert.deepStrictEqual(events, ['output:auth ready', 'close']);
});

test('runAuth returns when its auth worker reports ready without waiting for worker cleanup', async () => {
  const worker = new EventEmitter();
  const events = [];
  worker.send = () => {
    queueMicrotask(() => worker.emit('message', { type: 'ready' }));
  };
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    spawnAuthWorker: () => worker,
    writeStdoutLine: async (line) => events.push(`output:${line}`),
  });

  assert.deepStrictEqual(events, [
    'output:auth ready',
    'disconnect',
    'unref',
  ]);
});

test('runAuth prints one worker handoff notice on stderr and waits for ready before settling', async () => {
  const worker = new EventEmitter();
  const stdout = [];
  const stderr = [];
  const events = [];
  worker.send = () => {
    queueMicrotask(() => {
      worker.emit('message', { type: 'notice', message: foreignOriginHandoffNotice });
      worker.emit('message', { type: 'notice', message: `${foreignOriginHandoffNotice} https://secret.example` });
      worker.emit('message', { type: 'ready' });
    });
  };
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    spawnAuthWorker: () => worker,
    writeStdoutLine: async (line) => {
      stdout.push(line);
      events.push('stdout');
    },
    writeStderrLine: (line) => {
      stderr.push(line);
      events.push('stderr');
    },
  });

  assert.deepStrictEqual(stderr, [foreignOriginHandoffNotice]);
  assert.deepStrictEqual(stdout, ['auth ready']);
  assert.deepStrictEqual(events, ['stderr', 'stdout', 'disconnect', 'unref']);
  assert.doesNotMatch(stderr.join('\n'), /https?:\/\/|secret|password|cookie|csrf/i);
});

test('runAuth keeps ready terminal behavior when handoff notice output fails', async () => {
  for (const writeStderrLine of [
    () => { throw new Error('stderr unavailable'); },
    async () => { throw new Error('stderr unavailable'); },
  ]) {
    const worker = new EventEmitter();
    const stdout = [];
    worker.send = () => {
      queueMicrotask(() => {
        worker.emit('message', { type: 'notice', message: foreignOriginHandoffNotice });
        worker.emit('message', { type: 'ready' });
      });
    };
    worker.disconnect = () => {};
    worker.unref = () => {};

    await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
      spawnAuthWorker: () => worker,
      writeStdoutLine: async (line) => stdout.push(line),
      writeStderrLine,
    });

    assert.deepStrictEqual(stdout, ['auth ready']);
  }
});

test('runAuth rejects when its auth worker reports an error without waiting for worker cleanup', async () => {
  const worker = new EventEmitter();
  const events = [];
  worker.send = () => {
    queueMicrotask(() => worker.emit('message', { type: 'error', message: 'login cancelled' }));
  };
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
      spawnAuthWorker: () => worker,
      writeStdoutLine: async () => events.push('unexpected output'),
    }),
    /login cancelled/,
  );

  assert.deepStrictEqual(events, ['disconnect', 'unref']);
});

test('runAuth rejects and releases a worker that exits before reporting a terminal result', async () => {
  const worker = new EventEmitter();
  const events = [];
  worker.send = () => queueMicrotask(() => worker.emit('exit', 2, null));
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
      spawnAuthWorker: () => worker,
      writeStdoutLine: async () => events.push('unexpected output'),
    }),
    /auth worker exited before reporting a result \(code=2, signal=none\)/,
  );

  assert.deepStrictEqual(events, ['disconnect', 'unref']);
});

test('runAuth releases its worker when the start IPC send throws', async () => {
  const worker = new EventEmitter();
  const events = [];
  worker.send = () => { throw new Error('IPC unavailable'); };
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
      spawnAuthWorker: () => worker,
      writeStdoutLine: async () => events.push('unexpected output'),
    }),
    /IPC unavailable/,
  );

  assert.deepStrictEqual(events, ['disconnect', 'unref']);
});

test('runAuth releases its worker when the start IPC send callback fails', async () => {
  const worker = new EventEmitter();
  const events = [];
  worker.send = (message, callback) => queueMicrotask(() => callback(new Error('IPC callback failed')));
  worker.disconnect = () => events.push('disconnect');
  worker.unref = () => events.push('unref');

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
      spawnAuthWorker: () => worker,
      writeStdoutLine: async () => events.push('unexpected output'),
    }),
    /IPC callback failed/,
  );

  assert.deepStrictEqual(events, ['disconnect', 'unref']);
});

test('runAuth starts the hidden worker without argv credentials and sends only safe auth settings', async () => {
  const worker = new EventEmitter();
  let forkCall;
  let startMessage;
  worker.send = (message) => {
    startMessage = message;
    queueMicrotask(() => worker.emit('message', { type: 'ready' }));
  };
  worker.disconnect = () => {};
  worker.unref = () => {};

  await runAuth({
    ...keychainArgs({ noAutoFill: true, profileDir: '' }),
    password: 'must-not-cross-ipc',
    totpSeed: 'must-not-cross-ipc',
    cookie: 'must-not-cross-ipc',
    csrf: 'must-not-cross-ipc',
  }, {
    forkProcess: (...call) => {
      forkCall = call;
      return worker;
    },
    writeStdoutLine: async () => {},
  });

  assert.deepStrictEqual(forkCall[1], []);
  assert.strictEqual(forkCall[2].detached, true);
  assert.deepStrictEqual(forkCall[2].stdio, ['ignore', 'ignore', 'ignore', 'ipc']);
  assert.strictEqual(forkCall[2].env.ALILOG_AUTH_WORKER, '1');
  assert.strictEqual(startMessage.type, 'start');
  assert.deepStrictEqual(Object.keys(startMessage.args).sort(), [
    'authFile',
    'command',
    'debug',
    'keychainService',
    'logstore',
    'noAutoFill',
    'profileDir',
    'project',
    'signinDomain',
    'timeout',
    'totpInputSelector',
    'totpKeychainService',
    'userFile',
    'username',
  ]);
  assert.doesNotMatch(JSON.stringify(startMessage), /must-not-cross-ipc/);
});

test('piped auth CLI returns after worker terminal without waiting for slow cleanup', () => {
  const script = `${__dirname}/../alilog`;
  const workerCode = [
    "process.on('message', () => {",
    "  process.send({ type: 'debug', message: 'auth: started 2026-07-20 12:00:00.000' });",
    "  process.send({ type: 'debug', message: 'auth: mode=headed 12:00:00.001' });",
    "  process.send({ type: 'ready' });",
    '  setTimeout(() => {}, 1200);',
    '});',
  ].join('\n');
  const parentCode = [
    "const { spawn } = require('node:child_process');",
    `const { runAuth } = require(${JSON.stringify(script)});`,
    `const workerCode = ${JSON.stringify(workerCode)};`,
    '(async () => {',
    "  await runAuth({ command: 'auth', noAutoFill: true, profileDir: '', debug: true }, {",
    "    forkProcess: (modulePath, argv, options) => spawn(process.execPath, ['-e', workerCode], options),",
    '  });',
    '})().catch((error) => {',
    "  console.error(`ERROR: ${error.message}`);",
    '  process.exit(1);',
    '});',
  ].join('\n');
  const startedAt = Date.now();
  const result = spawnSync(process.execPath, ['-e', parentCode], {
    encoding: 'utf8',
    timeout: 3000,
  });
  const elapsedMs = Date.now() - startedAt;

  assert.strictEqual(result.status, 0, result.stderr);
  assert.match(result.stdout, /^auth: started 2026-07-20 12:00:00\.000/);
  assert.match(result.stdout, /auth: mode=headed 12:00:00\.001/);
  assert.match(result.stdout, /auth ready\n$/);
  assert.strictEqual(result.stderr, '');
  assert.ok(elapsedMs < 800, `piped auth waited ${elapsedMs}ms for worker cleanup`);
});

test('alilog production code contains no hidden pipe-test authentication bypass', () => {
  const source = fs.readFileSync(`${__dirname}/../alilog`, 'utf8');
  assert.doesNotMatch(source, /NODE_TEST_CONTEXT|alilog-worker-pipe-test/);
});

test('hidden auth worker sends its terminal result before cleanup and then exits', async () => {
  const channel = new EventEmitter();
  const events = [];
  channel.connected = true;
  channel.send = (message, callback) => {
    events.push(`send:${message.type}`);
    callback();
  };
  channel.disconnect = () => {
    channel.connected = false;
    events.push('disconnect');
  };

  const worker = runAuthWorkerProcess(channel, {
    executeAuth: async (workerArgs, { reportAuthReady }) => {
      events.push(`execute:${workerArgs.command}`);
      await reportAuthReady();
      events.push('cleanup');
    },
    exit: (code) => events.push(`exit:${code}`),
  });
  channel.emit('message', { type: 'start', args: { command: 'auth' } });
  await worker;

  assert.deepStrictEqual(events, [
    'execute:auth',
    'send:ready',
    'disconnect',
    'cleanup',
    'exit:0',
  ]);
});

test('hidden auth worker sends one nonterminal handoff notice and disconnects only after ready', async () => {
  const channel = new EventEmitter();
  const events = [];
  const sent = [];
  channel.connected = true;
  channel.send = (message, callback) => {
    sent.push(message);
    events.push(`send:${message.type}`);
    if (message.type !== 'notice') callback();
  };
  channel.disconnect = () => {
    channel.connected = false;
    events.push('disconnect');
  };

  const worker = runAuthWorkerProcess(channel, {
    executeAuth: async (workerArgs, { reportAuthNotice, reportAuthReady }) => {
      events.push(`execute:${workerArgs.command}`);
      await reportAuthNotice();
      assert.strictEqual(channel.connected, true);
      await reportAuthNotice();
      assert.strictEqual(channel.connected, true);
      await reportAuthReady();
    },
    exit: (code) => events.push(`exit:${code}`),
  });
  channel.emit('message', { type: 'start', args: { command: 'auth' } });
  await worker;

  assert.deepStrictEqual(sent, [
    { type: 'notice', message: foreignOriginHandoffNotice },
    { type: 'ready' },
  ]);
  assert.deepStrictEqual(events, [
    'execute:auth',
    'send:notice',
    'send:ready',
    'disconnect',
    'exit:0',
  ]);
});

test('hidden auth worker sends only its first terminal result and redacts error secrets', async () => {
  const channel = new EventEmitter();
  const sent = [];
  channel.connected = true;
  channel.send = (message, callback) => {
    sent.push(message);
    callback();
  };
  channel.disconnect = () => { channel.connected = false; };

  const worker = runAuthWorkerProcess(channel, {
    executeAuth: async (workerArgs, { reportAuthError, reportAuthReady }) => {
      await reportAuthError(new Error('password=private cookie=session'));
      await reportAuthReady();
    },
    exit: () => {},
  });
  channel.emit('message', { type: 'start', args: { command: 'auth' } });
  await worker;

  assert.strictEqual(sent.length, 1);
  assert.strictEqual(sent[0].type, 'error');
  assert.doesNotMatch(sent[0].message, /private|session/);
});

test('auth worker reports ready only after auth capture and persistence complete', async () => {
  const events = [];
  let finishPersistence;
  let persistenceStarted;
  const started = new Promise((resolve) => { persistenceStarted = resolve; });
  const persisted = new Promise((resolve) => { finishPersistence = resolve; });

  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({ name: 'headed' }),
    captureAuthWithBrowser: async () => {
      events.push('capture');
      persistenceStarted();
      await persisted;
      events.push('persisted');
    },
    reportAuthReady: async () => events.push('ready'),
    disposeBrowserSession: async () => events.push('cleanup'),
  });

  await started;
  assert.deepStrictEqual(events, ['capture']);
  finishPersistence();
  await auth;
  assert.deepStrictEqual(events, ['capture', 'persisted', 'ready', 'cleanup']);
});

test('runAuth forwards a headed handoff notice from browser capture without settling auth', async () => {
  const events = [];

  await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    automationMode: 'auto-fill',
    browserMode: 'headed',
    prepareAutoFillPlan: async () => ({
      username: 'alice@example.com',
      password: 'private-password',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }),
    newBrowserContext: async () => ({ name: 'headed' }),
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode, { reportAuthNotice }) => {
      events.push('capture');
      await reportAuthNotice();
      events.push('captured');
    },
    reportAuthNotice: () => events.push('notice'),
    reportAuthReady: async () => events.push('ready'),
    disposeBrowserSession: async () => events.push('cleanup'),
  });

  assert.deepStrictEqual(events, ['capture', 'notice', 'captured', 'ready', 'cleanup']);
});

test('auth worker reports its terminal error before browser cleanup completes', async () => {
  const events = [];
  let finishCleanup;
  const cleanupFinished = new Promise((resolve) => { finishCleanup = resolve; });
  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({ name: 'headed' }),
    captureAuthWithBrowser: async () => {
      events.push('capture');
      throw new Error('login cancelled');
    },
    reportAuthError: async (error) => events.push(`error:${error.message}`),
    disposeBrowserSession: async () => {
      events.push('cleanup:start');
      await cleanupFinished;
      events.push('cleanup:done');
    },
  });

  await new Promise((resolve) => setImmediate(resolve));
  const eventsBeforeCleanupFinishes = [...events];
  finishCleanup();
  await auth.catch(() => {});

  assert.deepStrictEqual(eventsBeforeCleanupFinishes, [
    'capture',
    'error:login cancelled',
    'cleanup:start',
  ]);
});

test('auth worker cleanup has a total budget when browser context close does not settle', async () => {
  let releaseContextClose;
  const contextCloseFinished = new Promise((resolve) => { releaseContextClose = resolve; });
  const browser = {
    context: {
      pages: () => [],
      close: async () => contextCloseFinished,
    },
    tempRoot: '',
  };

  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '/tmp/alilog-profile' }), {
    newBrowserContext: async () => browser,
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => {},
    cleanupTimeoutMs: 10,
  });
  const result = await Promise.race([
    auth.then(() => 'finished'),
    new Promise((resolve) => setTimeout(() => resolve('timed-out'), 100)),
  ]);
  releaseContextClose();
  await auth;

  assert.strictEqual(result, 'finished');
});

test('auth worker cleanup still attempts temporary profile removal when context close does not settle', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const events = [];
  let markCloseStarted;
  const closeStarted = new Promise((resolve) => { markCloseStarted = resolve; });
  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({
      context: {},
      tempRoot: '/tmp/alilog-auth-owned-profile',
    }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    closeBrowserContext: async () => {
      events.push('close');
      markCloseStarted();
      await new Promise(() => {});
    },
    removeBrowserProfile: async (tempRoot) => events.push(`remove:${tempRoot}`),
    reportCleanupEvent: (event) => events.push(event),
    cleanupTimeoutMs: 100,
  });

  await closeStarted;
  t.mock.timers.tick(99);
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepStrictEqual(events, [
    'ready',
    'close',
    'browser cleanup: context close timed out',
    'remove:/tmp/alilog-auth-owned-profile',
  ]);
  await auth;
});

test('auth worker cleanup removes its temporary profile even when context close fails', async () => {
  const events = [];
  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({
      context: {},
      tempRoot: '/tmp/alilog-auth-owned-profile',
    }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    closeBrowserContext: async () => {
      events.push('close');
      throw new Error('context close failed');
    },
    removeBrowserProfile: async (tempRoot) => events.push(`remove:${tempRoot}`),
    reportCleanupEvent: (event) => events.push(event),
  });

  assert.deepStrictEqual(events, [
    'ready',
    'close',
    'browser cleanup: context close failed',
    'remove:/tmp/alilog-auth-owned-profile',
  ]);
});

test('auth worker cleanup bounds a hanging temporary profile removal', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const events = [];
  let markRemoveStarted;
  const removeStarted = new Promise((resolve) => { markRemoveStarted = resolve; });
  const auth = runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({
      context: {},
      tempRoot: '/tmp/alilog-auth-owned-profile',
    }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    closeBrowserContext: async () => events.push('close'),
    removeBrowserProfile: async () => {
      events.push('remove');
      markRemoveStarted();
      await new Promise(() => {});
    },
    reportCleanupEvent: (event) => events.push(event),
    cleanupTimeoutMs: 100,
  });

  await removeStarted;
  let state = 'pending';
  auth.then(() => { state = 'finished'; });
  t.mock.timers.tick(19);
  await Promise.resolve();
  assert.strictEqual(state, 'pending');

  t.mock.timers.tick(1);
  await auth;
  assert.strictEqual(state, 'finished');
  assert.deepStrictEqual(events, [
    'ready',
    'close',
    'remove',
    'browser cleanup: temporary profile removal timed out',
  ]);
});

test('auth worker cleanup reports temporary profile removal failure without changing ready', async () => {
  const events = [];
  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({
      context: {},
      tempRoot: '/tmp/alilog-auth-owned-profile',
    }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    closeBrowserContext: async () => events.push('close'),
    removeBrowserProfile: async () => {
      events.push('remove');
      throw new Error('sensitive filesystem failure detail');
    },
    reportCleanupEvent: (event) => events.push(event),
  });

  assert.deepStrictEqual(events, [
    'ready',
    'close',
    'remove',
    'browser cleanup: temporary profile removal failed',
  ]);
  assert.doesNotMatch(events.join('\n'), /sensitive filesystem failure detail/);
});

test('auth worker cleanup never removes an explicit profile directory', async () => {
  const events = [];
  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '/tmp/alilog-explicit-profile' }), {
    newBrowserContext: async () => ({ context: {}, tempRoot: '' }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    closeBrowserContext: async () => events.push('close'),
    removeBrowserProfile: async () => events.push('remove'),
    reportCleanupEvent: (event) => events.push(event),
  });

  assert.deepStrictEqual(events, ['ready', 'close']);
});

test('auth worker keeps its ready result when browser cleanup throws synchronously', async () => {
  const events = [];
  await runAuth(keychainArgs({ noAutoFill: true, profileDir: '' }), {
    newBrowserContext: async () => ({ name: 'headed' }),
    captureAuthWithBrowser: async () => {},
    reportAuthReady: async () => events.push('ready'),
    disposeBrowserSession: () => {
      events.push('cleanup');
      throw new Error('cleanup failed synchronously');
    },
  });

  assert.deepStrictEqual(events, ['ready', 'cleanup']);
});

test('captureSlsAuth keeps the headless-browser timeout free of manual Search guidance', async () => {
  const page = new EventEmitter();
  const authCaptured = captureSlsAuth(page, {}, { timeout: 0.001 }, {
    timeoutMessage: 'headless SLS auth response was not observed',
  });

  await assert.rejects(authCaptured, (error) => {
    assert.match(error.message, /headless SLS auth response was not observed/);
    assert.doesNotMatch(error.message, /Search/);
    return true;
  });
});

test('captureSlsAuth keeps headed auth open after the SLS console is reached', async () => {
  const page = new EventEmitter();
  const mainFrame = {};
  const abortController = new AbortController();
  let currentUrl = 'https://signin.aliyun.com/login';
  page.url = () => currentUrl;
  page.mainFrame = () => mainFrame;

  const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
    abortSignal: abortController.signal,
    browserMode: 'headed',
    consoleQueryTimeoutMs: 1,
  });

  currentUrl = 'https://sls.console.aliyun.com/lognext/project/project/logsearch/logstore';
  page.emit('framenavigated', mainFrame);
  const state = await Promise.race([
    authCaptured.then(() => 'resolved', () => 'rejected'),
    new Promise((resolve) => setTimeout(() => resolve('pending'), 20)),
  ]);

  assert.strictEqual(state, 'pending');
  abortController.abort(new Error('test stop'));
  await assert.rejects(authCaptured, /test stop/);
});

test('captureSlsAuth limits console getLogs evidence to the console query timeout', async () => {
  const page = new EventEmitter();
  const mainFrame = {};
  let currentUrl = 'https://signin.aliyun.com/login';
  page.url = () => currentUrl;
  page.mainFrame = () => mainFrame;

  const authCaptured = captureSlsAuth(page, {}, { timeout: 1 }, {
    browserMode: 'headless',
    consoleQueryTimeoutMs: 1,
    timeoutMessage: 'headless SLS auth response was not observed',
  });

  currentUrl = 'https://sls.console.aliyun.com/lognext/project/project/logsearch/logstore';
  page.emit('framenavigated', mainFrame);

  await assert.rejects(authCaptured, /SLS console reached but no valid getLogs response was observed/);
});

test('captureSlsAuth gives default headless console queries fifteen seconds', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const page = new EventEmitter();
  page.url = () => 'https://sls.console.aliyun.com/lognext/project/project/logsearch/logstore';

  const authCaptured = captureSlsAuth(page, {}, { timeout: 60 }, {
    browserMode: 'headless',
  });
  let state = 'pending';
  authCaptured.then(
    () => { state = 'resolved'; },
    () => { state = 'rejected'; },
  );

  t.mock.timers.tick(8000);
  await Promise.resolve();
  assert.strictEqual(state, 'pending');

  t.mock.timers.tick(6999);
  await Promise.resolve();
  assert.strictEqual(state, 'pending');

  t.mock.timers.tick(1);
  await assert.rejects(authCaptured, /SLS console reached but no valid getLogs response was observed/);
});

test('browser auth lifecycle exits when the login tab is closed', () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const browser = new EventEmitter();
  context.pages = () => [page];
  context.browser = () => browser;
  const calls = [];

  const lifecycle = installBrowserAuthCloseHandlers(context, (error) => {
    calls.push(error);
  });
  if (lifecycle.getPageCount() === 0) lifecycle.markPage(page);

  page.emit('close');

  assert.strictEqual(calls.length, 1);
  assert.match(calls[0].message, /登录已取消或浏览器已关闭/);
});

test('alilog CLI help and invalid args have expected process behavior', () => {
  const script = `${__dirname}/../alilog`;
  const help = execFileSync(process.execPath, [script, '--help'], { encoding: 'utf8' });
  assert.match(help, /^usage: scripts\/alilog auth /);
  assert.match(help, /commands:/);
  assert.doesNotMatch(help, /query output:/);
  assert.doesNotMatch(help, /help:/);

  const queryHelp = execFileSync(process.execPath, [script, 'query', '--help'], { encoding: 'utf8' });
  assert.match(queryHelp, /^usage: scripts\/alilog query /);
  assert.match(queryHelp, /query syntax: SLS syntax, not natural language/);
  assert.match(queryHelp, /--query '\*'/);
  assert.match(queryHelp, /--query '_container_name_: svc and error'/);
  assert.match(queryHelp, /--query 'content:prefix\*'/);
  assert.match(queryHelp, /Prefer count\/top\/group by first/);
  assert.match(queryHelp, /last_1m\|last_5m\|last_15m\|last_1h\|last_4h\|last_1d\|last_3d\|last_1w/);
  assert.match(queryHelp, /--continue INDEX:OFFSET continues one selected log body; it is not pagination/);
  assert.match(queryHelp, /search request id, TID text, or internal log text in indexed content/);
  assert.match(queryHelp, /confirm real fields with fields before --extra-fields/);
  assert.doesNotMatch(queryHelp, /--raw/);
  assert.doesNotMatch(queryHelp, /tid\/request id/);
  assert.doesNotMatch(queryHelp, /scripts\/alilog auth /);

  const fieldsHelp = execFileSync(process.execPath, [script, 'fields', '--help'], { encoding: 'utf8' });
  assert.match(fieldsHelp, /^usage: scripts\/alilog fields /);
  assert.match(fieldsHelp, /sampled_logs/);
  assert.match(fieldsHelp, /time: same as query, for example last_15m, now-30m, now-15m~now-5m, today/);
  assert.doesNotMatch(fieldsHelp, /--raw/);

  const logstoresHelp = execFileSync(process.execPath, [script, 'logstores', '--help'], { encoding: 'utf8' });
  assert.match(logstoresHelp, /^usage: scripts\/alilog logstores /);
  assert.match(logstoresHelp, /--keyword/);
  assert.doesNotMatch(logstoresHelp, /--query QUERY/);

  const authHelp = execFileSync(process.execPath, [script, 'auth', '--help'], { encoding: 'utf8' });
  assert.match(authHelp, /^usage: scripts\/alilog auth /);
  assert.match(authHelp, /target hint/);
  assert.doesNotMatch(authHelp, /--query QUERY/);

  assert.match(queryHelp, /SLS syntax, not natural language/);
  assert.match(queryHelp, /--query '\*'/);
  assert.match(queryHelp, /--query '_container_name_: svc and error'/);
  assert.match(queryHelp, /--query 'content:prefix\*'/);
  assert.match(queryHelp, /Prefer count\/top\/group by first/);
  assert.doesNotMatch(help, /SLS syntax, not natural language/);

  const invalid = spawnSync(process.execPath, [script, 'query', '--bad'], { encoding: 'utf8' });
  assert.notStrictEqual(invalid.status, 0);
  assert.match(invalid.stderr, /ERROR: unknown argument: --bad/);
});

test('SLS docs keep alilog query and auth guidance aligned with CLI contract', () => {
  const skillRoot = `${__dirname}/../..`;
  const skill = fs.readFileSync(`${skillRoot}/SKILL.md`, 'utf8');
  const sls = fs.readFileSync(`${skillRoot}/references/sls.md`, 'utf8');
  const firstUse = fs.readFileSync(`${skillRoot}/references/first-use.md`, 'utf8');

  assert.match(skill, /执行工具命令时正常等待进程结束后再读取输出/);
  assert.match(skill, /references\/first-use\.md/);
  assert.match(sls, /SLS 查询不提供 raw/);
  assert.doesNotMatch(sls, /--raw/);
  assert.doesNotMatch(sls, /--extra-fields[^\n]*tid/);
  assert.match(sls, /TID 通常是正文文本，不是稳定字段名/);
  assert.match(sls, /scripts\/alilog index-fields --project/);
  assert.match(sls, /`keys` 不是所有合法查询字段/);
  assert.match(sls, /`fields` 表示某个查询、时间范围和样本日志中实际观察到的字段/);
  assert.match(sls, /`lastModifyTime \+ ttl`/);
  assert.match(sls, /完整父路径/);
  assert.match(sls, /没有 `line` 不等于不能裸词查询/);
  assert.match(sls, /`alias`[^\n]*分析语句[^\n]*字段查询[^\n]*原始字段名/);
  assert.match(sls, /`include_keys`[^\n]*`exclude_keys`/);
  assert.match(sls, /`max_depth=-1`[^\n]*不限深度/);
  assert.match(sls, /`doc_value=false`[^\n]*不代表[^\n]*字段索引[^\n]*`field:value`/);
  assert.match(sls, /不会主动清除浏览器 cookie/);
  assert.doesNotMatch(sls, /清除浏览器中的旧 SLS 登录态/);
  assert.match(sls, /并输出 `auth ready`/);
  assert.match(sls, /无头 auto-login/);
  assert.match(sls, /有头 auto-fill/);
  assert.match(sls, /有头 auto-fill 只补空的账号、密码和 TOTP/);
  assert.match(sls, /不覆盖用户输入或点击登录、验证按钮/);
  assert.match(sls, /不会将本地 TOTP 填入短信验证码/);
  assert.match(sls, /共用 2 次自动恢复机会，耗尽后转为手动登录/);
  assert.match(sls, /账号\/密码或 TOTP 安全码错误会立即停止自动填充/);
  assert.match(sls, /scripts\/alilog auth --no-auto-fill/);
  assert.match(sls, /auth --no-auto-fill` 从一开始走完全手动登录，[^。\n]*不读取本地账号、密码或 TOTP/);
  assert.match(sls, /更新 Keychain 中 `alilog` 的密码或 `alilog-totp` 的 TOTP seed/);
  assert.match(sls, /scripts\/alilog auth --debug/);
  assert.match(firstUse, /scripts\/skillctl setup --check/);
  assert.match(firstUse, /security add-generic-password[^\n]*-s alilog(?:\s|$)/);
  assert.match(firstUse, /security add-generic-password[^\n]*-s alilog-totp(?:\s|$)/);
  assert.match(firstUse, /scripts\/alilog auth/);
});

test('alilog query reports likely unquoted shell glob after --query', () => {
  const script = `${__dirname}/../alilog`;
  const result = spawnSync(process.execPath, [
    script,
    'query',
    '--project', 'proj',
    '--logstore', 'store',
    '--from', '2026-06-12 13:49:13',
    '--to', '2026-06-12 14:04:13',
    '--query', 'alilog',
    'dbops-query',
  ], { encoding: 'utf8' });

  assert.notStrictEqual(result.status, 0);
  assert.match(result.stderr, /unexpected argument after --query/);
  assert.match(result.stderr, /quote the query/);
  assert.match(result.stderr, /--query '\*'/);
});

test('alilog auth help exposes target hints without removed force-login', () => {
  const script = `${__dirname}/../alilog`;
  const help = execFileSync(process.execPath, [script, 'auth', '--help'], { encoding: 'utf8' });

  assert.match(help, /alilog auth/);
  assert.match(help, /--project PROJECT/);
  assert.match(help, /--logstore LOGSTORE/);
  assert.doesNotMatch(help, /--force-login/);
});

test('deleted params fail as unknown args', () => {
  const deleted = [
    ['--container', 'svc'],
    ['--auto-login'],
    ['--username', 'user'],
    ['--user-file', 'file'],
    ['--auth-file', 'file'],
    ['--signin-domain', 'example.com'],
    ['--keychain-service', 'svc'],
    ['--totp-keychain-service', 'svc'],
    ['--totp-input-selector', 'input'],
    ['--totp-submit-selector', 'button'],
  ];

  for (const argv of deleted) {
    assertThrowsMessage(() => queryArgs(argv), new RegExp(`unknown argument: ${argv[0]}`));
  }
});

test('useful auth and query params still parse', () => {
  const auth = parseArgs([
    'auth',
    '--project', 'proj',
    '--logstore', 'store',
    '--no-auto-fill',
    '--timeout', '300',
    '--debug',
  ]);
  assert.strictEqual(auth.noAutoFill, true);
  assert.strictEqual(auth.timeout, 300);
  assert.strictEqual(auth.debug, true);
  assertThrowsMessage(() => parseArgs(['auth', '--force-login']), /unknown argument: --force-login/);

  const query = queryArgs([
    '--page', '2',
    '--size', '5',
    '--expand-sql',
    '--continue', '1:1200',
    '--select-fields', 'content,level,content',
    '--extra-fields', 'thread,content,thread',
  ]);
  assert.strictEqual(query.page, 2);
  assert.strictEqual(query.size, 5);
  assert.strictEqual(query.expandSql, true);
  assert.strictEqual(query.continueAt, '1:1200');
  assert.deepStrictEqual(query.selectFields, ['content', 'level']);
  assert.deepStrictEqual(query.extraFields, ['thread', 'content']);

  const fields = fieldsArgs();
  assert.strictEqual(fields.command, 'fields');
  assert.strictEqual(fields.size, 20);
});

test('query size defaults to 10 and is capped at 100', () => {
  assert.strictEqual(queryArgs().size, 10);
  assert.strictEqual(queryArgs(['--size', '100']).size, 100);
  assertThrowsMessage(() => queryArgs(['--size', '101']), /--size must be an integer between 1 and 100/);
});

test('auth defaults to alilog Keychain service names', () => {
  const oldKeychainService = process.env.ALILOG_KEYCHAIN_SERVICE;
  const oldTotpKeychainService = process.env.ALILOG_TOTP_KEYCHAIN_SERVICE;
  delete process.env.ALILOG_KEYCHAIN_SERVICE;
  delete process.env.ALILOG_TOTP_KEYCHAIN_SERVICE;
  try {
    const auth = parseArgs(['auth']);
    assert.strictEqual(auth.keychainService, 'alilog');
    assert.strictEqual(auth.totpKeychainService, 'alilog-totp');
  } finally {
    if (oldKeychainService === undefined) {
      delete process.env.ALILOG_KEYCHAIN_SERVICE;
    } else {
      process.env.ALILOG_KEYCHAIN_SERVICE = oldKeychainService;
    }
    if (oldTotpKeychainService === undefined) {
      delete process.env.ALILOG_TOTP_KEYCHAIN_SERVICE;
    } else {
      process.env.ALILOG_TOTP_KEYCHAIN_SERVICE = oldTotpKeychainService;
    }
  }
});

test('readUsernameFromKeychainAccount parses acct from Keychain output', async () => {
  const calls = [];
  const username = await readUsernameFromKeychainAccount(keychainArgs(), {
    platform: 'darwin',
    execFileAsync: async (command, argv, options) => {
      calls.push({ command, argv, options });
      return { stdout: '    "acct"<blob>="user@example.com"\n', stderr: '' };
    },
  });

  assert.strictEqual(username, 'user@example.com');
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].command, 'security');
  assert.deepStrictEqual(calls[0].argv, ['find-generic-password', '-s', 'alilog']);
  assert.strictEqual(calls[0].options.encoding, 'utf8');
});

test('readUsernameFromKeychainAccount falls back to TOTP service account', async () => {
  const services = [];
  const username = await readUsernameFromKeychainAccount(keychainArgs(), {
    platform: 'darwin',
    execFileAsync: async (command, argv) => {
      const service = argv[argv.indexOf('-s') + 1];
      services.push(service);
      if (service === 'alilog') throw new Error('not found');
      return { stdout: '', stderr: '    "acct"<blob>=" fallback@example.com "\n' };
    },
  });

  assert.strictEqual(username, 'fallback@example.com');
  assert.deepStrictEqual(services, ['alilog', 'alilog-totp']);
});

test('readUsernameFromKeychainAccount returns empty outside macOS', async () => {
  let called = false;
  const username = await readUsernameFromKeychainAccount(keychainArgs(), {
    platform: 'linux',
    execFileAsync: async () => {
      called = true;
      return { stdout: '    "acct"<blob>="user@example.com"\n', stderr: '' };
    },
  });

  assert.strictEqual(username, '');
  assert.strictEqual(called, false);
});

test('readPasswordFromKeychain prefers env and reads macOS Keychain', async () => {
  let calledForEnv = false;
  const envPassword = await readPasswordFromKeychain(keychainArgs({ username: 'user@example.com' }), {
    env: { ALILOG_PASSWORD: 'env-password' },
    platform: 'darwin',
    execFileAsync: async () => {
      calledForEnv = true;
      return { stdout: 'keychain-password\n' };
    },
  });
  assert.strictEqual(envPassword, 'env-password');
  assert.strictEqual(calledForEnv, false);

  const calls = [];
  const password = await readPasswordFromKeychain(keychainArgs({ username: 'user@example.com' }), {
    env: {},
    platform: 'darwin',
    execFileAsync: async (command, argv, options) => {
      calls.push({ command, argv, options });
      return { stdout: 'keychain-password\n' };
    },
  });

  assert.strictEqual(password, 'keychain-password');
  assert.strictEqual(calls[0].command, 'security');
  assert.deepStrictEqual(calls[0].argv, [
    'find-generic-password',
    '-s', 'alilog',
    '-a', 'user@example.com',
    '-w',
  ]);
  assert.strictEqual(calls[0].options.encoding, 'utf8');
});

test('readPasswordFromKeychain reports missing password source clearly', async () => {
  await assert.rejects(
    () => readPasswordFromKeychain(keychainArgs({ username: 'user@example.com' }), {
      env: {},
      platform: 'linux',
      execFileAsync: async () => ({ stdout: 'password\n' }),
    }),
    /ALILOG_PASSWORD is required on non-macOS platforms/,
  );

  await assert.rejects(
    () => readPasswordFromKeychain(keychainArgs({ username: 'user@example.com' }), {
      env: {},
      platform: 'darwin',
      execFileAsync: async () => ({ stdout: '\n' }),
    }),
    /failed to read password from Keychain service=alilog/,
  );
});

test('readTotpSeedFromKeychain prefers env and reads macOS Keychain', async () => {
  let calledForEnv = false;
  const envSeed = await readTotpSeedFromKeychain(keychainArgs({ username: 'user@example.com' }), {
    env: { ALILOG_TOTP_SEED: 'ENVSEED' },
    platform: 'darwin',
    execFileAsync: async () => {
      calledForEnv = true;
      return { stdout: 'KEYCHAINSEED\n' };
    },
  });
  assert.strictEqual(envSeed, 'ENVSEED');
  assert.strictEqual(calledForEnv, false);

  const calls = [];
  const seed = await readTotpSeedFromKeychain(keychainArgs({ username: 'user@example.com' }), {
    env: {},
    platform: 'darwin',
    execFileAsync: async (command, argv, options) => {
      calls.push({ command, argv, options });
      return { stdout: 'KEYCHAINSEED\n' };
    },
  });

  assert.strictEqual(seed, 'KEYCHAINSEED');
  assert.strictEqual(calls[0].command, 'security');
  assert.deepStrictEqual(calls[0].argv, [
    'find-generic-password',
    '-s', 'alilog-totp',
    '-a', 'user@example.com',
    '-w',
  ]);
  assert.strictEqual(calls[0].options.encoding, 'utf8');
});

test('readTotpSeedFromKeychain reports missing seed source clearly', async () => {
  await assert.rejects(
    () => readTotpSeedFromKeychain(keychainArgs({ username: 'user@example.com' }), {
      env: {},
      platform: 'linux',
      execFileAsync: async () => ({ stdout: 'SEED\n' }),
    }),
    /ALILOG_TOTP_SEED is required on non-macOS platforms/,
  );

  await assert.rejects(
    () => readTotpSeedFromKeychain(keychainArgs({ username: 'user@example.com' }), {
      env: {},
      platform: 'darwin',
      execFileAsync: async () => ({ stdout: '\n' }),
    }),
    /failed to read TOTP seed from Keychain service=alilog-totp/,
  );
});

test('supported TOTP configuration accepts only SHA1, 6 digits, and 30 seconds', () => {
  const seed = 'JBSWY3DPEHPK3PXP';
  assert.strictEqual(parseSupportedTotpSeed(seed), seed);
  assert.strictEqual(
    parseSupportedTotpSeed(`otpauth://totp/Aliyun?secret=${seed}&algorithm=SHA1&digits=6&period=30`),
    seed,
  );
  assert.strictEqual(parseSupportedTotpSeed(`otpauth://totp/Aliyun?secret=${seed}&algorithm=SHA256`), null);
  assert.strictEqual(parseSupportedTotpSeed(`otpauth://totp/Aliyun?secret=${seed}&digits=8`), null);
  assert.strictEqual(parseSupportedTotpSeed(`otpauth://totp/Aliyun?secret=${seed}&period=60`), null);
  assert.strictEqual(parseSupportedTotpSeed(`otpauth://hotp/Aliyun?secret=${seed}`), null);
  assert.strictEqual(parseSupportedTotpSeed('not-a-base32-seed!'), null);
});

test('Aliyun headless-browser auto-login requires complete supported local credentials', () => {
  const complete = { username: 'user@example.com', password: 'password', totpSeed: 'JBSWY3DPEHPK3PXP' };
  assert.strictEqual(canUseHeadlessAliyunLogin({ noAutoFill: false, profileDir: '' }, complete), true);
  assert.strictEqual(canUseHeadlessAliyunLogin({ noAutoFill: true, profileDir: '' }, complete), false);
  assert.strictEqual(canUseHeadlessAliyunLogin({ noAutoFill: false, profileDir: '' }, { ...complete, totpSeed: null }), false);
  assert.strictEqual(canUseHeadlessAliyunLogin({ noAutoFill: false, profileDir: '/tmp/profile' }, complete), false);
});

test('default auth mode follows the complete eight-combination fillable credential matrix', () => {
  const expectedByBits = {
    '000': { automationMode: 'manual', browserMode: 'headed' },
    '001': { automationMode: 'auto-fill', browserMode: 'headed' },
    '010': { automationMode: 'auto-fill', browserMode: 'headed' },
    '011': { automationMode: 'auto-fill', browserMode: 'headed' },
    '100': { automationMode: 'auto-fill', browserMode: 'headed' },
    '101': { automationMode: 'auto-fill', browserMode: 'headed' },
    '110': { automationMode: 'auto-fill', browserMode: 'headed' },
    '111': { automationMode: 'auto-login', browserMode: 'headless' },
  };

  for (const [bits, expected] of Object.entries(expectedByBits)) {
    const [hasUsername, hasPassword, hasTotp] = bits.split('').map((bit) => bit === '1');
    const plan = {
      username: hasUsername ? 'user@example.com' : '',
      password: hasPassword ? 'password' : null,
      totpSeed: hasTotp ? 'JBSWY3DPEHPK3PXP' : null,
    };
    assert.deepStrictEqual(
      selectAliyunAuthMode({ noAutoFill: false, profileDir: '' }, plan),
      expected,
      `unexpected auth mode for username/password/totp=${bits}`,
    );
  }
});

test('profile-dir and unsupported TOTP preserve the fillable-field mode boundary', () => {
  const complete = { username: 'user@example.com', password: 'password', totpSeed: 'JBSWY3DPEHPK3PXP' };
  const empty = { username: '', password: null, totpSeed: null };

  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '/tmp/profile' }, complete), {
    automationMode: 'auto-fill',
    browserMode: 'headed',
  });
  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '/tmp/profile' }, empty), {
    automationMode: 'manual',
    browserMode: 'headed',
  });
  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '' }, {
    ...empty,
    totpUnsupported: true,
  }), {
    automationMode: 'manual',
    browserMode: 'headed',
  });
  for (const plan of [
    { ...empty, username: 'user@example.com', totpUnsupported: true },
    { ...empty, password: 'password', totpUnsupported: true },
  ]) {
    assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '' }, plan), {
      automationMode: 'auto-fill',
      browserMode: 'headed',
    });
  }
});

test('default mode uses resolved fillable values regardless of their credential source', () => {
  const resolvedPlans = [
    ['ALILOG_USERNAME', { username: 'user@example.com', password: null, totpSeed: null }],
    ['user file', { username: 'user@example.com', password: null, totpSeed: null }],
    ['Keychain account', { username: 'user@example.com', password: null, totpSeed: null }],
    ['ALILOG_PASSWORD', { username: '', password: 'password', totpSeed: null }],
    ['Keychain password', { username: '', password: 'password', totpSeed: null }],
    ['ALILOG_TOTP_SEED', { username: '', password: null, totpSeed: 'JBSWY3DPEHPK3PXP' }],
    ['Keychain TOTP', { username: '', password: null, totpSeed: 'JBSWY3DPEHPK3PXP' }],
  ];

  for (const [source, plan] of resolvedPlans) {
    assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '' }, plan), {
      automationMode: 'auto-fill',
      browserMode: 'headed',
    }, `resolved credentials from ${source} must use the same mode rule`);
  }
});

test('missing macOS security command preserves manual, partial auto-fill, and complete headless modes', async () => {
  const originalUsername = process.env.ALILOG_USERNAME;
  delete process.env.ALILOG_USERNAME;
  const unavailableSecurity = async () => {
    const error = new Error('spawn /private/bin/security ENOENT apiKey=private-key');
    error.code = 'ENOENT';
    error.path = '/private/bin/security';
    throw error;
  };

  async function resolvePlan({ username = '', userFileUsername = '', env = {} }) {
    const authArgs = keychainArgs({
      username,
      noAutoFill: false,
      profileDir: '',
      debug: true,
    });
    await applyUserConfig(authArgs, {
      readFile: async () => {
        if (!userFileUsername) throw new Error('missing user file');
        return JSON.stringify({ username: userFileUsername });
      },
      readUsernameFromKeychainAccount: (targetArgs) => readUsernameFromKeychainAccount(targetArgs, {
        platform: 'darwin',
        execFileAsync: unavailableSecurity,
      }),
    });

    const plan = {
      username: authArgs.username,
      password: null,
      totpSeed: null,
      totpUnsupported: false,
      passwordChecked: false,
      totpChecked: false,
    };
    const errors = [];
    if (env.ALILOG_PASSWORD || plan.username) {
      plan.passwordChecked = true;
      try {
        plan.password = await readPasswordFromKeychain(authArgs, {
          env,
          platform: 'darwin',
          execFileAsync: unavailableSecurity,
        });
      } catch (error) {
        errors.push(error.message);
      }
    }
    if (env.ALILOG_TOTP_SEED || plan.username) {
      plan.totpChecked = true;
      try {
        const seed = await readTotpSeedFromKeychain(authArgs, {
          env,
          platform: 'darwin',
          execFileAsync: unavailableSecurity,
        });
        plan.totpSeed = parseSupportedTotpSeed(seed);
      } catch (error) {
        errors.push(error.message);
      }
    }
    return { authArgs, plan, errors };
  }

  try {
    const cases = [
      [
        await resolvePlan({}),
        { automationMode: 'manual', browserMode: 'headed' },
      ],
      [
        await resolvePlan({ userFileUsername: 'partial@example.com' }),
        { automationMode: 'auto-fill', browserMode: 'headed' },
      ],
      [
        await resolvePlan({
          username: 'complete@example.com',
          env: {
            ALILOG_PASSWORD: 'private-password',
            ALILOG_TOTP_SEED: 'JBSWY3DPEHPK3PXP',
          },
        }),
        { automationMode: 'auto-login', browserMode: 'headless' },
      ],
    ];

    const logs = await captureConsoleLogs(async () => {
      for (const [{ authArgs, plan, errors }, expectedMode] of cases) {
        const observed = [];
        await runAuth(authArgs, {
          prepareAutoFillPlan: async () => plan,
          newBrowserContext: async (args, headless) => {
            observed.push({ headless });
            return { name: headless ? 'headless' : 'headed' };
          },
          captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
            observed.push({ authMode });
          },
          disposeBrowserSession: async () => {},
          reportAuthReady: async () => {},
        });

        assert.deepStrictEqual(observed, [
          { headless: expectedMode.browserMode === 'headless' },
          { authMode: expectedMode },
        ]);
        assert.doesNotMatch(errors.join('\n'), /ENOENT|private\/bin|private-key|private-password/i);
      }
    });

    assert.doesNotMatch(
      logs.join('\n'),
      /ENOENT|private\/bin|private-key|private-password|complete@example|partial@example|JBSWY/i,
    );
  } finally {
    if (originalUsername === undefined) delete process.env.ALILOG_USERNAME;
    else process.env.ALILOG_USERNAME = originalUsername;
  }
});

test('internal auth modes select supported browser and automation combinations', () => {
  const complete = { username: 'user@example.com', password: 'password', totpSeed: 'JBSWY3DPEHPK3PXP' };

  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '' }, complete), {
    automationMode: 'auto-login',
    browserMode: 'headless',
  });
  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: false, profileDir: '/tmp/profile' }, complete), {
    automationMode: 'auto-fill',
    browserMode: 'headed',
  });
  assert.deepStrictEqual(selectAliyunAuthMode({ noAutoFill: true, profileDir: '' }, complete), {
    automationMode: 'manual',
    browserMode: 'headed',
  });
  assertThrowsMessage(() => selectAliyunAuthMode({ noAutoFill: true }, complete, {
    automationMode: 'auto-fill',
    browserMode: 'headed',
  }), /--no-auto-fill requires manual headed auth mode/);
  assert.deepStrictEqual(selectAliyunAuthMode({}, null, {
    automationMode: 'auto-login',
    browserMode: 'headed',
  }), {
    automationMode: 'auto-login',
    browserMode: 'headed',
  });

  assertThrowsMessage(() => selectAliyunAuthMode({}, null, { automationMode: 'auto-fill' }), /both automationMode and browserMode/);
  assertThrowsMessage(() => selectAliyunAuthMode({}, null, { browserMode: 'headed' }), /both automationMode and browserMode/);
  assertThrowsMessage(() => selectAliyunAuthMode({}, null, {
    automationMode: 'auto-fill',
    browserMode: 'headless',
  }), /unsupported Aliyun auth mode/);
  assertThrowsMessage(() => selectAliyunAuthMode({}, null, {
    automationMode: 'manual',
    browserMode: 'headless',
  }), /unsupported Aliyun auth mode/);
});

test('--no-auto-fill does not read username sources, create an auto-fill plan, or use headless', async () => {
  const originalUsername = process.env.ALILOG_USERNAME;
  process.env.ALILOG_USERNAME = 'env-user@example.com';
  const authArgs = parseArgs(['auth', '--no-auto-fill']);
  assert.strictEqual(authArgs.username, '');
  let usernameSourceReads = 0;
  try {
    await applyUserConfig(authArgs, {
      readFile: async () => {
        usernameSourceReads += 1;
        throw new Error('must not read user file');
      },
      readUsernameFromKeychainAccount: async () => {
        usernameSourceReads += 1;
        throw new Error('must not read Keychain');
      },
    });
    assert.strictEqual(usernameSourceReads, 0);
    assert.strictEqual(authArgs.username, '');
  } finally {
    if (originalUsername === undefined) delete process.env.ALILOG_USERNAME;
    else process.env.ALILOG_USERNAME = originalUsername;
  }

  const browserModes = [];
  await runAuth(authArgs, {
    prepareAutoFillPlan: async () => {
      throw new Error('must not create auto-fill plan');
    },
    newBrowserContext: async (args, headless) => {
      browserModes.push(headless);
      return { name: 'manual' };
    },
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
      assert.strictEqual(autoFillPlan, null);
      assert.deepStrictEqual(authMode, { automationMode: 'manual', browserMode: 'headed' });
    },
    disposeBrowserSession: async () => {},
    writeStdoutLine: async () => {},
  });
  assert.deepStrictEqual(browserModes, [false]);
});

test('default runAuth keeps its empty plan and opens only headed manual auth', async () => {
  const emptyPlan = {
    username: '',
    password: null,
    totpSeed: null,
    totpUnsupported: false,
    passwordChecked: false,
    totpChecked: false,
  };
  const browser = { name: 'headed' };
  const createdModes = [];
  const captures = [];

  await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => emptyPlan,
    newBrowserContext: async (args, headless) => {
      createdModes.push(headless ? 'headless' : 'headed');
      return browser;
    },
    captureAuthWithBrowser: async (capturedBrowser, args, autoFillPlan, authMode) => {
      captures.push({ capturedBrowser, autoFillPlan, authMode });
    },
    disposeBrowserSession: async () => {},
    reportAuthReady: async () => {},
  });

  assert.deepStrictEqual(createdModes, ['headed']);
  assert.strictEqual(captures.length, 1);
  assert.strictEqual(captures[0].capturedBrowser, browser);
  assert.strictEqual(captures[0].autoFillPlan, emptyPlan);
  assert.deepStrictEqual(captures[0].authMode, {
    automationMode: 'manual',
    browserMode: 'headed',
  });
});

test('invalid internal auth mode rejects before browser creation', async () => {
  await assert.rejects(
    runAuth(keychainArgs(), {
      automationMode: 'manual',
      browserMode: 'headless',
      newBrowserContext: async () => {
        throw new Error('browser must not start');
      },
    }),
    /unsupported Aliyun auth mode/,
  );
});

test('explicit manual auth mode does not prepare local credentials', async () => {
  const browserModes = [];
  await runAuth(keychainArgs(), {
    automationMode: 'manual',
    browserMode: 'headed',
    prepareAutoFillPlan: async () => {
      throw new Error('must not prepare local credentials');
    },
    newBrowserContext: async (args, headless) => {
      browserModes.push(headless);
      return { name: 'manual' };
    },
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
      assert.strictEqual(autoFillPlan, null);
      assert.deepStrictEqual(authMode, { automationMode: 'manual', browserMode: 'headed' });
    },
    disposeBrowserSession: async () => {},
    writeStdoutLine: async () => {},
  });
  assert.deepStrictEqual(browserModes, [false]);
});

test('partial internal auth override rejects before credential preparation or browser creation', async () => {
  await assert.rejects(
    runAuth(keychainArgs(), {
      automationMode: 'auto-login',
      prepareAutoFillPlan: async () => {
        throw new Error('must not prepare local credentials');
      },
      newBrowserContext: async () => {
        throw new Error('browser must not start');
      },
    }),
    /both automationMode and browserMode/,
  );
});

test('applyUserConfig resolves username by explicit arg file then Keychain account', async () => {
  const originalUsername = process.env.ALILOG_USERNAME;
  delete process.env.ALILOG_USERNAME;

  try {
    const explicit = keychainArgs({ username: 'explicit@example.com' });
    await applyUserConfig(explicit, {
      readFile: async () => {
        throw new Error('should not read user file');
      },
      readUsernameFromKeychainAccount: async () => {
        throw new Error('should not read Keychain');
      },
    });
    assert.strictEqual(explicit.username, 'explicit@example.com');

    const fromFile = keychainArgs();
    await applyUserConfig(fromFile, {
      readFile: async () => '{"username":" file@example.com "}',
      readUsernameFromKeychainAccount: async () => 'keychain@example.com',
    });
    assert.strictEqual(fromFile.username, 'file@example.com');

    const fromKeychain = keychainArgs();
    await applyUserConfig(fromKeychain, {
      readFile: async () => {
        throw new Error('missing file');
      },
      readUsernameFromKeychainAccount: async () => 'keychain@example.com',
    });
    assert.strictEqual(fromKeychain.username, 'keychain@example.com');
  } finally {
    if (originalUsername === undefined) delete process.env.ALILOG_USERNAME;
    else process.env.ALILOG_USERNAME = originalUsername;
  }
});

test('applyUserConfig uses ALILOG_USERNAME before local username sources', async () => {
  const originalUsername = process.env.ALILOG_USERNAME;
  process.env.ALILOG_USERNAME = 'env-user@example.com';
  const authArgs = keychainArgs();

  try {
    await applyUserConfig(authArgs, {
      readFile: async () => {
        throw new Error('must not read user file');
      },
      readUsernameFromKeychainAccount: async () => {
        throw new Error('must not read Keychain');
      },
    });
    assert.strictEqual(authArgs.username, 'env-user@example.com');
  } finally {
    if (originalUsername === undefined) delete process.env.ALILOG_USERNAME;
    else process.env.ALILOG_USERNAME = originalUsername;
  }
});

test('auth success output is compact plain text', () => {
  const text = formatAuthSuccessOutput();

  assert.strictEqual(text, 'auth ready');
  assertThrowsMessage(() => JSON.parse(text), /Unexpected token|Unexpected end/);
  assert.doesNotMatch(text, /ok|msg|auth_file|generated_at/);
});

test('auth debug starts with a full timestamp and keeps later timestamps compact', async () => {
  const logs = await captureConsoleLogs(() => runAuth(
    keychainArgs({ noAutoFill: false, profileDir: '', debug: true }),
    {
      prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
      newBrowserContext: async () => ({ name: 'headless' }),
      captureAuthWithBrowser: async () => {},
      disposeBrowserSession: async () => {},
      writeStdoutLine: async () => {},
    },
  ));

  assert.match(logs[0], /^auth: started \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$/);
  assert.match(logs[1], /^auth: mode=headless \d{2}:\d{2}:\d{2}\.\d{3}$/);
});

test('runAuth writes auth ready before awaiting temporary browser close', async () => {
  const headlessBrowser = { name: 'headless' };
  const browserModes = [];
  const captured = [];
  const events = [];

  const result = await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
    newBrowserContext: async (args, headless) => {
      browserModes.push(headless);
      return headless ? headlessBrowser : null;
    },
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
      captured.push({ browser, authMode });
    },
    writeStdoutLine: async (line) => events.push(`output:${line}`),
    disposeBrowserSession: async (browser) => {
      events.push(`close:start:${browser.name}`);
      await Promise.resolve();
      events.push(`close:done:${browser.name}`);
    },
  });

  assert.deepStrictEqual(browserModes, [true]);
  assert.deepStrictEqual(captured, [{
    browser: headlessBrowser,
    authMode: { automationMode: 'auto-login', browserMode: 'headless' },
  }]);
  assert.deepStrictEqual(events, [
    'output:auth ready',
    'close:start:headless',
    'close:done:headless',
  ]);
  assert.strictEqual(result, undefined);
});

test('runAuth keeps explicit diagnostic profile on the normal close path', async () => {
  const browser = { name: 'headed' };
  const events = [];

  const result = await runAuth(keychainArgs({ noAutoFill: true, profileDir: '/tmp/alilog-profile' }), {
    newBrowserContext: async (args, headless) => {
      assert.strictEqual(headless, false);
      return browser;
    },
    captureAuthWithBrowser: async () => {},
    writeStdoutLine: async (line) => events.push(`output:${line}`),
    disposeBrowserSession: async (candidate) => events.push(`close:${candidate.name}`),
  });

  assert.strictEqual(result, undefined);
  assert.deepStrictEqual(events, ['output:auth ready', 'close:headed']);
});

test('captureAuthWithBrowser retries one auto-login captcha in the same page and context', async () => {
  const events = [];
  let resolveAuth;
  const page = {
    once() {},
    isClosed() { return false; },
  };
    const context = {
      pages() { return [page]; },
      once() {},
      on() {},
      browser() { return null; },
  };
  let autoLoginAttempts = 0;

  await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
    username: 'alice@example.com',
    password: 'pw',
    totpSeed: 'JBSWY3DPEHPK3PXP',
  }, { automationMode: 'auto-login', browserMode: 'headless' }, {
    captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
      events.push('capture');
      resolveAuth = resolve;
      abortSignal.addEventListener('abort', () => reject(abortSignal.reason), { once: true });
    }),
    openLoginPage: async () => { events.push('open'); },
    restartAliyunLoginFlow: async () => { events.push('restart'); },
    runAliyunLoginAutomation: async () => {
      autoLoginAttempts += 1;
      events.push(`auto-login:${autoLoginAttempts}`);
      if (autoLoginAttempts === 1) throw new Error('Aliyun auto-login stopped: captcha');
      resolveAuth();
    },
  });

  assert.strictEqual(autoLoginAttempts, 2);
  assert.deepStrictEqual(events, ['capture', 'open', 'auto-login:1', 'restart', 'auto-login:2']);
});

test('captureAuthWithBrowser aborts pending response capture when login navigation fails', async () => {
  let captureAborted = false;
  const page = {
    once() {},
    isClosed() { return false; },
  };
  const context = {
    pages() { return [page]; },
    once() {},
    on() {},
    browser() { return null; },
  };

  await assert.rejects(
    captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
      username: 'alice@example.com',
      password: 'pw',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }, { automationMode: 'auto-login', browserMode: 'headless' }, {
      captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
        abortSignal.addEventListener('abort', () => {
          captureAborted = true;
          reject(abortSignal.reason);
        }, { once: true });
      }),
      openLoginPage: async () => {
        throw new Error('navigation unavailable');
      },
    }),
    /navigation unavailable/,
  );

  assert.strictEqual(captureAborted, true);
});

test('captureAuthWithBrowser removes browser lifecycle listeners when login navigation fails', async () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const browser = new EventEmitter();
  page.isClosed = () => false;
  page.url = () => 'https://signin.aliyun.com/example/login.htm#/main';
  page.mainFrame = () => page;
  context.pages = () => [page];
  context.browser = () => browser;

  await assert.rejects(
    captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false, timeout: 1 }), null, {
      automationMode: 'manual',
      browserMode: 'headed',
    }, {
      openLoginPage: async () => {
        throw new Error('navigation unavailable');
      },
    }),
    /navigation unavailable/,
  );

  assert.strictEqual(page.listenerCount('response'), 0);
  assert.strictEqual(page.listenerCount('framenavigated'), 0);
  assert.strictEqual(page.listenerCount('close'), 0);
  assert.strictEqual(context.listenerCount('close'), 0);
  assert.strictEqual(context.listenerCount('page'), 0);
  assert.strictEqual(browser.listenerCount('disconnected'), 0);
});

test('captureAuthWithBrowser removes browser lifecycle listeners after auth capture succeeds', async () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const browser = new EventEmitter();
  page.isClosed = () => false;
  context.pages = () => [page];
  context.browser = () => browser;

  await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), null, {
    automationMode: 'manual',
    browserMode: 'headed',
  }, {
    captureSlsAuth: async () => {},
    openLoginPage: async () => {},
  });

  assert.strictEqual(page.listenerCount('close'), 0);
  assert.strictEqual(context.listenerCount('close'), 0);
  assert.strictEqual(context.listenerCount('page'), 0);
  assert.strictEqual(browser.listenerCount('disconnected'), 0);
});

test('captureAuthWithBrowser forwards headed auto-fill handoff notice and continues response capture', async () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const events = [];
  page.isClosed = () => false;
  page.url = () => 'https://signin.aliyun.com/example/login.htm#/main';
  context.pages = () => [page];
  context.browser = () => null;

  await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
    username: 'alice@example.com',
    password: 'private-password',
    totpSeed: 'JBSWY3DPEHPK3PXP',
  }, {
    automationMode: 'auto-fill',
    browserMode: 'headed',
  }, {
    captureSlsAuth: async () => {
      await new Promise((resolve) => setImmediate(resolve));
      events.push('capture-ready');
    },
    openLoginPage: async () => events.push('open'),
    runAliyunAutoFillMonitor: async (capturedPage, capturedArgs, { reportNotice }) => {
      events.push('auto-fill');
      await reportNotice();
      events.push('notice-sent');
    },
    reportAuthNotice: () => events.push('notice'),
  });

  assert.deepStrictEqual(events, [
    'open',
    'auto-fill',
    'notice',
    'notice-sent',
    'capture-ready',
  ]);
});

test('captureAuthWithBrowser skips manual guidance when the page is already SLS or foreign', async () => {
  for (const currentUrl of [
    'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store',
    'https://example.com/login',
  ]) {
    const page = new EventEmitter();
    const context = new EventEmitter();
    let injected = 0;
    page.isClosed = () => false;
    page.url = () => currentUrl;
    page.evaluate = async () => { injected += 1; };
    context.pages = () => [page];
    context.browser = () => null;

    await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
      username: '',
      password: null,
      totpSeed: null,
      totpUnsupported: false,
    }, {
      automationMode: 'manual',
      browserMode: 'headed',
    }, {
      captureSlsAuth: async () => {},
      openLoginPage: async () => {},
    });

    assert.strictEqual(injected, 0, currentUrl);
  }
});

test('captureAuthWithBrowser shows existing zero-field guidance for default empty manual auth', async () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const notices = [];
  const events = [];
  const emptyPlan = {
    username: '',
    password: null,
    totpSeed: null,
    totpUnsupported: false,
  };
  page.isClosed = () => false;
  page.url = () => 'https://signin.aliyun.com/example/login.htm#/main';
  page.evaluate = async (pageFunction, message) => {
    notices.push(String(message));
    events.push('notice');
  };
  context.pages = () => [page];
  context.browser = () => null;

  await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), emptyPlan, {
    automationMode: 'manual',
    browserMode: 'headed',
  }, {
    captureSlsAuth: async () => { events.push('capture-ready'); },
    openLoginPage: async () => { events.push('open'); },
    runAliyunAutoFillMonitor: async () => {
      throw new Error('auto-fill monitor must not start for empty manual auth');
    },
  });

  assert.deepStrictEqual(events, ['capture-ready', 'open', 'notice']);
  assert.deepStrictEqual(notices, [[
    '登录辅助准备完成',
    '未读取到可自动填充的账号、密码、安全码',
    '请手动填写并点击登录/提交；脚本会在登录成功后保存 SLS 登录态。',
    '自动填充配置见 references/first-use.md。',
  ].join('\n')]);
});

test('captureAuthWithBrowser shows the hard credential guidance before waiting for headed manual completion', async () => {
  const page = new EventEmitter();
  const context = new EventEmitter();
  const notices = [];
  page.isClosed = () => false;
  page.url = () => 'https://signin.aliyun.com/example/login.htm#/main';
  page.evaluate = async (pageFunction, message) => { notices.push(String(message)); };
  context.pages = () => [page];
  context.browser = () => null;

  await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
    username: 'alice@example.com',
    password: 'saved-password',
    totpSeed: 'JBSWY3DPEHPK3PXP',
  }, {
    automationMode: 'manual',
    browserMode: 'headed',
    feedbackKind: 'password_rejected',
  }, {
    captureSlsAuth: async () => {},
    openLoginPage: async () => {},
  });

  assert.strictEqual(notices.length, 1);
  assert.match(notices[0], /账号或密码错误，自动填充已停止/);
  assert.match(notices[0], /关闭当前窗口，检查账号并更新 Keychain 密码/);
  assert.doesNotMatch(notices[0], /saved-password|alice@example\.com|JBSWY/);
});

test('captureAuthWithBrowser stops after the second auto-login captcha without another restart', async () => {
  const events = [];
  const page = {
    once() {},
    isClosed() { return false; },
  };
  const context = {
    pages() { return [page]; },
    once() {},
    on() {},
    browser() { return null; },
  };
  let autoLoginAttempts = 0;

  await assert.rejects(
    captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
      username: 'alice@example.com',
      password: 'pw',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }, { automationMode: 'auto-login', browserMode: 'headed' }, {
      captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
        events.push('capture');
        abortSignal.addEventListener('abort', () => reject(abortSignal.reason), { once: true });
      }),
      openLoginPage: async () => { events.push('open'); },
      restartAliyunLoginFlow: async () => { events.push('restart'); },
      runAliyunLoginAutomation: async () => {
        autoLoginAttempts += 1;
        events.push(`auto-login:${autoLoginAttempts}`);
        throw new Error('Aliyun auto-login stopped: captcha');
      },
    }),
    /Aliyun auto-login stopped: captcha/,
  );

  assert.strictEqual(autoLoginAttempts, 2);
  assert.deepStrictEqual(events, ['capture', 'open', 'auto-login:1', 'restart', 'auto-login:2']);
});

for (const feedbackKind of ['password_rejected', 'totp_rejected']) {
  test(`captureAuthWithBrowser does not retry auto-login ${feedbackKind}`, async () => {
    const events = [];
    const page = {
      once() {},
      isClosed() { return false; },
    };
    const context = {
      pages() { return [page]; },
      once() {},
      on() {},
      browser() { return null; },
    };

    await assert.rejects(
      captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
        username: 'alice@example.com',
        password: 'pw',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      }, { automationMode: 'auto-login', browserMode: 'headless' }, {
        captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
          abortSignal.addEventListener('abort', () => reject(abortSignal.reason), { once: true });
        }),
        openLoginPage: async () => {},
        restartAliyunLoginFlow: async () => { events.push('restart'); },
        runAliyunLoginAutomation: async () => {
          events.push('auto-login');
          throw new Error(`Aliyun auto-login stopped: ${feedbackKind}`);
        },
      }),
      new RegExp(feedbackKind),
    );

    assert.deepStrictEqual(events, ['auto-login']);
  });
}

test('captureAuthWithBrowser retries one unrecognized visible login error before failing', async () => {
  const events = [];
  const page = { once() {}, isClosed() { return false; } };
  const context = {
    pages() { return [page]; },
    once() {},
    on() {},
    browser() { return null; },
  };
  let attempts = 0;

  await assert.rejects(
    captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
      username: 'alice@example.com',
      password: 'pw',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }, { automationMode: 'auto-login', browserMode: 'headless' }, {
      captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
        abortSignal.addEventListener('abort', () => reject(abortSignal.reason), { once: true });
      }),
      openLoginPage: async () => {},
      restartAliyunLoginFlow: async () => { events.push('restart'); },
      runAliyunLoginAutomation: async () => {
        attempts += 1;
        events.push(`auto-login:${attempts}`);
        throw new Error('Aliyun auto-login stopped: login_feedback_unrecognized');
      },
    }),
    /login_feedback_unrecognized/,
  );

  assert.deepStrictEqual(events, ['auto-login:1', 'restart', 'auto-login:2']);
});

test('explicit headless auto-login failure closes and rejects without headed fallback', async () => {
  const headlessBrowser = { name: 'headless' };
  const headlessFailure = new Error('Aliyun auto-login stopped: captcha');
  const browserModes = [];
  const closed = [];
  const outputs = [];

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
      automationMode: 'auto-login',
      browserMode: 'headless',
      prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
      newBrowserContext: async (args, headless) => {
        browserModes.push(headless);
        return headless ? headlessBrowser : { name: 'headed' };
      },
      captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
        if (authMode.browserMode === 'headless') throw headlessFailure;
        throw new Error('headed auth should not start');
      },
      disposeBrowserSession: async (browser) => {
        if (browser) closed.push(browser);
      },
      writeStdoutLine: async (line) => outputs.push(line),
    }),
    (error) => error === headlessFailure,
  );

  assert.deepStrictEqual(browserModes, [true]);
  assert.deepStrictEqual(closed, [headlessBrowser]);
  assert.deepStrictEqual(outputs, []);
});

test('explicit headless auto-login context creation fails without headed fallback', async () => {
  const headlessFailure = new Error('headless browser unavailable');
  const browserModes = [];

  await assert.rejects(
    runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
      automationMode: 'auto-login',
      browserMode: 'headless',
      prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
      newBrowserContext: async (args, headless) => {
        browserModes.push(headless);
        throw headlessFailure;
      },
      captureAuthWithBrowser: async () => {
        throw new Error('auth capture must not start');
      },
    }),
    (error) => error === headlessFailure,
  );

  assert.deepStrictEqual(browserModes, [true]);
});

test('runAuth default mode falls back to headed auto-fill when headless context creation fails', async () => {
  const headedBrowser = { name: 'headed' };
  const events = [];

  await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
    newBrowserContext: async (args, headless) => {
      events.push(`create:${headless ? 'headless' : 'headed'}`);
      if (headless) throw new Error('headless browser unavailable');
      return headedBrowser;
    },
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
      events.push(`capture:${authMode.browserMode}`);
    },
    disposeBrowserSession: async (browser) => events.push(`dispose:${browser.name}`),
    writeStdoutLine: async (line) => events.push(`output:${line}`),
  });

  assert.deepStrictEqual(events, [
    'create:headless',
    'create:headed',
    'capture:headed',
    'output:auth ready',
    'dispose:headed',
  ]);
});

test('runAuth default mode falls back to headed auto-fill after a final headless captcha', async () => {
  const headlessBrowser = { name: 'headless' };
  const headedBrowser = { name: 'headed' };
  const events = [];

  const dependencies = {
    prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
    newBrowserContext: async (args, headless) => {
      events.push(`create:${headless ? 'headless' : 'headed'}`);
      return headless ? headlessBrowser : headedBrowser;
    },
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
      events.push(`capture:${authMode.browserMode}`);
      if (authMode.browserMode === 'headless') throw new Error('Aliyun auto-login stopped: captcha');
    },
    disposeBrowserSession: async (browser) => events.push(`dispose:${browser.name}`),
    writeStdoutLine: async (line) => events.push(`output:${line}`),
  };
  const debugLogs = await captureConsoleLogs(() => runAuth(
    keychainArgs({ noAutoFill: false, profileDir: '', debug: true }),
    dependencies,
  ));

  assert.deepStrictEqual(events, [
    'create:headless',
    'capture:headless',
    'create:headed',
    'dispose:headless',
    'capture:headed',
    'output:auth ready',
    'dispose:headed',
  ]);
  assert.match(debugLogs.join('\n'), /mode=headless/);
  assert.match(debugLogs.join('\n'), /headless fallback: Aliyun auto-login stopped: captcha/);
  assert.match(debugLogs.join('\n'), /mode=headed/);
});

test('runAuth keeps headless foreign-origin fallback and reports notice only from headed auto-fill', async () => {
  const events = [];

  await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => ({
      username: 'alice@example.com',
      password: 'private-password',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }),
    newBrowserContext: async (args, headless) => ({
      name: headless ? 'headless' : 'headed',
    }),
    captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode, { reportAuthNotice }) => {
      events.push(`capture:${authMode.browserMode}`);
      if (authMode.browserMode === 'headless') {
        throw new Error('Aliyun auto-login stopped: foreign_origin');
      }
      await reportAuthNotice();
      events.push('headed-captured');
    },
    reportAuthNotice: async () => events.push('notice'),
    reportAuthReady: async () => events.push('ready'),
    disposeBrowserSession: async (browser) => events.push(`dispose:${browser.name}`),
  });

  assert.deepStrictEqual(events, [
    'capture:headless',
    'dispose:headless',
    'capture:headed',
    'notice',
    'headed-captured',
    'ready',
    'dispose:headed',
  ]);
});

for (const [feedbackKind, expectedGuidanceKind] of [
  ['password_rejected', 'password_rejected'],
  ['totp_rejected', 'totp_rejected'],
]) {
  test(`runAuth default mode hands ${feedbackKind} to headed manual without rereading credentials`, async () => {
    const events = [];
    let prepareCount = 0;
    let readyCount = 0;

    await runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
      prepareAutoFillPlan: async () => {
        prepareCount += 1;
        return { username: 'alice@example.com', password: 'saved-password', totpSeed: 'JBSWY3DPEHPK3PXP' };
      },
      newBrowserContext: async (args, headless) => ({ name: headless ? 'headless' : 'headed' }),
      captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
        events.push({ browser: browser.name, autoFillPlan, authMode });
        if (browser.name === 'headless') throw new Error(`Aliyun auto-login stopped: ${feedbackKind}`);
      },
      disposeBrowserSession: async () => {},
      reportAuthReady: async () => { readyCount += 1; },
    });

    assert.strictEqual(prepareCount, 1);
    assert.deepStrictEqual(events.map(({ browser, authMode }) => ({ browser, authMode })), [
      { browser: 'headless', authMode: { automationMode: 'auto-login', browserMode: 'headless' } },
      {
        browser: 'headed',
        authMode: { automationMode: 'manual', browserMode: 'headed', feedbackKind: expectedGuidanceKind },
      },
    ]);
    assert.strictEqual(events[0].autoFillPlan, events[1].autoFillPlan);
    assert.strictEqual(readyCount, 1);
  });
}

test('each new auth run prepares a fresh credential snapshot', async () => {
  const capturedPasswords = [];
  let prepareCount = 0;
  const dependencies = {
    prepareAutoFillPlan: async () => {
      prepareCount += 1;
      return {
        username: 'alice@example.com',
        password: prepareCount === 1 ? 'first-snapshot' : 'second-snapshot',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      };
    },
    newBrowserContext: async () => ({ name: 'headless' }),
    captureAuthWithBrowser: async (browser, args, autoFillPlan) => {
      capturedPasswords.push(autoFillPlan.password);
    },
    disposeBrowserSession: async () => {},
    reportAuthReady: async () => {},
  };

  await runAuth(keychainArgs({ noAutoFill: false }), dependencies);
  await runAuth(keychainArgs({ noAutoFill: false }), dependencies);

  assert.strictEqual(prepareCount, 2);
  assert.deepStrictEqual(capturedPasswords, ['first-snapshot', 'second-snapshot']);
});

test('default headed fallback does not wait for temporary headless browser cleanup', async () => {
  const headlessBrowser = { name: 'headless' };
  const headedBrowser = { name: 'headed' };
  const events = [];
  let finishHeadlessCleanup;
  const headlessCleanupFinished = new Promise((resolve) => { finishHeadlessCleanup = resolve; });
  const auth = runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
    newBrowserContext: async (args, headless) => {
      events.push(`create:${headless ? 'headless' : 'headed'}`);
      return headless ? headlessBrowser : headedBrowser;
    },
    captureAuthWithBrowser: async (browser) => {
      events.push(`capture:${browser.name}`);
      if (browser === headlessBrowser) throw new Error('headless failed');
    },
    disposeBrowserSession: async (browser) => {
      events.push(`dispose:${browser.name}:start`);
      if (browser === headlessBrowser) await headlessCleanupFinished;
      events.push(`dispose:${browser.name}:done`);
    },
    reportAuthReady: async () => events.push('ready'),
  });
  let authSettled = false;
  auth.then(() => { authSettled = true; });

  await new Promise((resolve) => setImmediate(resolve));
  const eventsBeforeHeadlessCleanup = [...events];
  const settledBeforeHeadlessCleanup = authSettled;
  finishHeadlessCleanup();
  await auth;

  assert.deepStrictEqual(eventsBeforeHeadlessCleanup.slice(0, 2), [
    'create:headless',
    'capture:headless',
  ]);
  assert.ok(eventsBeforeHeadlessCleanup.includes('dispose:headless:start'));
  assert.ok(eventsBeforeHeadlessCleanup.includes('create:headed'));
  assert.ok(eventsBeforeHeadlessCleanup.includes('capture:headed'));
  assert.ok(eventsBeforeHeadlessCleanup.includes('ready'));
  assert.doesNotMatch(eventsBeforeHeadlessCleanup.join('\n'), /dispose:headless:done/);
  assert.strictEqual(settledBeforeHeadlessCleanup, false);
  assert.match(events.join('\n'), /dispose:headless:done/);
});

test('retired and current browser cleanup share one bounded terminal budget', async () => {
  const headlessBrowser = { name: 'headless' };
  const headedBrowser = { name: 'headed' };
  const cleanupStarts = [];
  const auth = runAuth(keychainArgs({ noAutoFill: false, profileDir: '' }), {
    prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
    newBrowserContext: async (args, headless) => headless ? headlessBrowser : headedBrowser,
    captureAuthWithBrowser: async (browser) => {
      if (browser === headlessBrowser) throw new Error('headless failed');
    },
    disposeBrowserSession: async (browser) => {
      cleanupStarts.push(browser.name);
      await new Promise(() => {});
    },
    reportAuthReady: async () => {},
    cleanupTimeoutMs: 10,
  });

  const result = await Promise.race([
    auth.then(() => 'finished'),
    new Promise((resolve) => setTimeout(() => resolve('timed-out'), 100)),
  ]);

  assert.strictEqual(result, 'finished');
  assert.deepStrictEqual(cleanupStarts, ['headless', 'headed']);
});

test('runAuth debug fallback does not expose an external headless error message', async () => {
  const headlessBrowser = { name: 'headless' };
  const headedBrowser = { name: 'headed' };
  const externalFailure = new Error('opaque-private-value=unstructured-secret RequestId: abc cookie=session');
  externalFailure.name = 'TimeoutError';
  const debugLogs = await captureConsoleLogs(() => runAuth(
    keychainArgs({ noAutoFill: false, profileDir: '', debug: true }),
    {
      prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
      newBrowserContext: async (args, headless) => headless ? headlessBrowser : headedBrowser,
      captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
        if (authMode.browserMode === 'headless') throw externalFailure;
      },
      writeStdoutLine: async () => {},
    },
  ));

  const output = debugLogs.join('\n');
  assert.match(output, /headless fallback: TimeoutError/);
  assert.doesNotMatch(output, /opaque-private-value|unstructured-secret|RequestId|cookie/i);
});

test('runAuth debug fallback keeps a safe internal auto-login category', async () => {
  const debugLogs = await captureConsoleLogs(() => runAuth(
    keychainArgs({ noAutoFill: false, profileDir: '', debug: true }),
    {
      prepareAutoFillPlan: async () => ({ username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' }),
      newBrowserContext: async (args, headless) => ({ name: headless ? 'headless' : 'headed' }),
      captureAuthWithBrowser: async (browser, args, autoFillPlan, authMode) => {
        if (authMode.browserMode === 'headless') {
          throw new Error('Aliyun auto-login stopped: password-submit_timeout');
        }
      },
      writeStdoutLine: async () => {},
    },
  ));

  assert.match(debugLogs.join('\n'), /headless fallback: Aliyun auto-login stopped: password-submit_timeout/);
});

test('capture boundary preserves browser cookies and routes automation by internal mode', async () => {
  async function captureForMode(authMode) {
    const events = [];
    const page = {
      once() {},
      isClosed() { return false; },
    };
    const context = {
      pages() { return []; },
      async newPage() {
        events.push('page');
        return page;
      },
      async clearCookies() { throw new Error('auth must not clear browser cookies'); },
      once() {},
      on() {},
      browser() { return null; },
    };
    await captureAuthWithBrowser({ context }, keychainArgs({ noAutoFill: false }), {
      username: 'alice@example.com',
      password: 'pw',
      totpSeed: 'JBSWY3DPEHPK3PXP',
    }, authMode, {
      captureSlsAuth: async () => { events.push('listener'); },
      openLoginPage: async () => { events.push('navigate'); },
      runAliyunLoginAutomation: async () => { events.push('auto-login'); },
      runAliyunAutoFillMonitor: async () => { events.push('auto-fill'); },
    });
    return events;
  }

  assert.deepStrictEqual(await captureForMode({ automationMode: 'auto-login', browserMode: 'headed' }), [
    'page', 'listener', 'navigate', 'auto-login',
  ]);
  assert.deepStrictEqual(await captureForMode({ automationMode: 'auto-fill', browserMode: 'headed' }), [
    'page', 'listener', 'navigate', 'auto-fill',
  ]);
  assert.deepStrictEqual(await captureForMode({ automationMode: 'manual', browserMode: 'headed' }), [
    'page', 'listener', 'navigate',
  ]);
});

test('auth defaults project and logstore when omitted', () => {
  const auth = parseArgs(['auth']);

  assert.strictEqual(auth.project, 'kuebernetes-production');
  assert.strictEqual(auth.logstore, 'production');
});

test('query still requires explicit project and logstore', () => {
  assertThrowsMessage(() => parseArgs([
    'query',
    '--logstore', 'store',
    '--query', '*',
    '--from', '2026-06-01 14:00:00',
    '--to', '2026-06-01 14:05:00',
  ]), /--project is required/);

  assertThrowsMessage(() => parseArgs([
    'query',
    '--project', 'proj',
    '--query', '*',
    '--from', '2026-06-01 14:00:00',
    '--to', '2026-06-01 14:05:00',
  ]), /--logstore is required/);
});

test('query refresh-auth and profile-dir are unavailable', () => {
  assertThrowsMessage(() => queryArgs(['--print-fields']), /unknown argument: --print-fields/);
  assertThrowsMessage(() => queryArgs(['--refresh-auth']), /unknown argument: --refresh-auth/);
  assertThrowsMessage(() => queryArgs(['--profile-dir', '/tmp/alilog-profile']), /unknown argument: --profile-dir/);
  assertThrowsMessage(() => queryArgs(['--timeout', '300']), /unknown argument: --timeout/);
  assertThrowsMessage(() => queryArgs(['--no-auto-fill']), /unknown argument: --no-auto-fill/);
  assertThrowsMessage(() => queryArgs(['--force-login']), /unknown argument: --force-login/);
  assertThrowsMessage(() => queryArgs(['--debug']), /unknown argument: --debug/);
  assertThrowsMessage(() => queryArgs(['--raw']), /unknown argument: --raw/);
});

test('auth rejects query-only args', () => {
  assertThrowsMessage(() => parseArgs(['auth', '--raw']), /unknown argument: --raw/);
  assertThrowsMessage(() => parseArgs(['auth', '--size', '20']), /unknown argument: --size/);
});

test('--profile-dir parses for auth only', () => {
  const auth = parseArgs([
    'auth',
    '--profile-dir', '/tmp/alilog-profile',
  ]);
  assert.strictEqual(auth.profileDir, '/tmp/alilog-profile');
});

test('login guidance message describes available auto-fill fields', () => {
  const full = loginAutoFillGuidanceMessage({
    canFillUsername: true,
    canFillPassword: true,
    canFillTotp: true,
  });
  assert.strictEqual(full, [
    '登录辅助已就绪',
    '账号、密码、安全码会在输入框为空时自动填充',
    '按钮需要你点击；你自己填写时，脚本不会拦截或覆盖。',
  ].join('\n'));
  assert.doesNotMatch(full, /首次|补空|空值补填|脚本刚填过|刷新|TOTP|Codex|等待中/);

  const partial = loginAutoFillGuidanceMessage({
    canFillUsername: true,
    canFillPassword: true,
    canFillTotp: false,
  });
  assert.strictEqual(partial, [
    '登录辅助已就绪',
    '账号、密码会在输入框为空时自动填充；安全码请手动填写',
    '按钮需要你点击；你自己填写时，脚本不会拦截或覆盖。',
    '自动填充配置见 references/first-use.md。',
  ].join('\n'));
  assert.doesNotMatch(partial, /首次|补空|空值补填|脚本刚填过|刷新|TOTP|Codex|等待中/);

  const none = loginAutoFillGuidanceMessage();
  assert.strictEqual(none, [
    '登录辅助准备完成',
    '未读取到可自动填充的账号、密码、安全码',
    '请手动填写并点击登录/提交；脚本会在登录成功后保存 SLS 登录态。',
    '自动填充配置见 references/first-use.md。',
  ].join('\n'));
  assert.doesNotMatch(none, /首次|补空|空值补填|脚本刚填过|刷新|TOTP|Codex|等待中/);
});

test('partial login guidance precisely lists every fillable field combination', () => {
  const cases = [
    [{ canFillUsername: true }, '账号会在输入框为空时自动填充；密码、安全码请手动填写'],
    [{ canFillPassword: true }, '密码会在输入框为空时自动填充；账号、安全码请手动填写'],
    [{ canFillTotp: true }, '安全码会在输入框为空时自动填充；账号、密码请手动填写'],
    [{ canFillUsername: true, canFillPassword: true }, '账号、密码会在输入框为空时自动填充；安全码请手动填写'],
    [{ canFillUsername: true, canFillTotp: true }, '账号、安全码会在输入框为空时自动填充；密码请手动填写'],
    [{ canFillPassword: true, canFillTotp: true }, '密码、安全码会在输入框为空时自动填充；账号请手动填写'],
  ];

  for (const [state, fieldLine] of cases) {
    assert.strictEqual(loginAutoFillGuidanceMessage(state), [
      '登录辅助已就绪',
      fieldLine,
      '按钮需要你点击；你自己填写时，脚本不会拦截或覆盖。',
      '自动填充配置见 references/first-use.md。',
    ].join('\n'));
  }
});

test('login guidance notice injection is cached by message and navigation', () => {
  const state = { message: '', navigationVersion: -1 };
  function markInjected(message, navigationVersion) {
    state.message = message;
    state.navigationVersion = navigationVersion;
  }

  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'ready', 0), true);
  markInjected('ready', 0);
  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'ready', 0), false);
  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'manual password', 0), true);
  markInjected('manual password', 0);
  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'manual password', 0), false);
  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'manual password', 1), true);
  markInjected('manual password', 1);
  assert.strictEqual(shouldInjectLoginGuidanceNotice(state, 'manual password', 1), false);
});

test('visible nocaptcha slider text is detected', () => {
  assert.strictEqual(detectCaptcha({
    '#nocaptcha.nc-container': captchaElement({ textContent: '请向右滑动验证' }),
  }), true);
});

test('visible nocaptcha dom without text is detected', () => {
  assert.strictEqual(detectCaptcha({
    '#nocaptcha.nc-container': captchaElement(),
  }), true);
});

test('visible nocaptcha failed text is detected', () => {
  assert.strictEqual(detectCaptcha({
    '#nocaptcha .nc_wrapper': captchaElement({ textContent: '验证失败，点击框体重试(error:83S1w5)' }),
  }), true);
});

test('hidden nocaptcha slider dom is ignored', () => {
  assert.strictEqual(detectCaptcha({
    '#nocaptcha.nc-container': captchaElement({ textContent: '请向右滑动验证', visible: false }),
    '#nocaptcha .btn_slide[aria-label="滑块"][role="button"]': captchaElement({ textContent: '向右滑动验证', visible: false }),
  }), false);
});

test('visible captcha feedback href is detected', () => {
  assert.strictEqual(detectCaptcha({
    '.bx-pu-qrcode-wrap #bx-feedback-btn': captchaElement({ href: 'https://example.com/?x5secdata=abc' }),
  }), true);
  assert.strictEqual(detectCaptcha({
    '.bx-pu-qrcode-wrap #bx-feedback-btn': captchaElement({ href: 'https://example.com/?_____tmd_____=abc' }),
  }), true);
});

test('visible baxia captcha iframe src is detected', () => {
  assert.strictEqual(detectCaptcha({
    'iframe#baxia-dialog-content': captchaElement({
      src: 'https://signin-cn-hangzhou.aliyun.com:443//entrance/_____tmd_____/punish?x5secdata=abc&action=captcha&pureCaptcha=true',
    }),
  }), true);
});

test('every supported Aliyun captcha DOM selector remains detectable', () => {
  for (const selector of [
    '#nocaptcha.nc-container',
    '#nocaptcha .nc_wrapper',
    '#nocaptcha .nc_scale',
    '#nocaptcha .btn_slide[aria-label="滑块"][role="button"]',
    '#nc_1_n1z.btn_slide[aria-label="滑块"]',
    '#nc_1__scale_text .nc-lang-cnt',
  ]) {
    assert.strictEqual(detectCaptcha({ [selector]: captchaElement() }), true, selector);
  }

  for (const selector of [
    'iframe#baxia-dialog-content',
    'iframe[src*="_____tmd_____"]',
    'iframe[src*="x5secdata"]',
    'iframe[src*="action=captcha"]',
    'iframe[src*="pureCaptcha=true"]',
  ]) {
    assert.strictEqual(detectCaptcha({
      [selector]: captchaElement({ src: 'https://signin.aliyun.com/risk?action=captcha&pureCaptcha=true' }),
    }), true, selector);
  }
});

test('hasAliyunCaptcha scans child frame captcha dom', async () => {
  const page = {
    frames() {
      return [
        fakeCaptchaFrame({}),
        fakeCaptchaFrame({
          '#nocaptcha .nc_wrapper': captchaElement({ textContent: '验证失败，点击框体重试(error:Ciafr5)' }),
        }),
      ];
    },
  };

  assert.strictEqual(await hasAliyunCaptcha(page), true);
});

test('hasAliyunCaptcha reads captcha iframe src through runtime href helper', async () => {
  const page = fakeCaptchaFrame({
    'iframe#baxia-dialog-content': captchaElement({
      src: 'https://signin-cn-hangzhou.aliyun.com:443//entrance/_____tmd_____/punish?x5secdata=abc&action=captcha&pureCaptcha=true',
    }),
  });

  assert.strictEqual(await hasAliyunCaptcha(page), true);
});

test('Aliyun feedback ignores current-looking errors inside a hidden child frame', async () => {
  const mainFrame = fakeCaptchaFrame({});
  const ariaHiddenFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({ textContent: '安全码错误。' }),
  });
  ariaHiddenFrame.frameElement = async () => ({
    async isVisible() { return true; },
    async evaluate() { return true; },
  });
  const layoutHiddenFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({ textContent: '用户名或密码错误。' }),
  });
  layoutHiddenFrame.frameElement = async () => ({ async isVisible() { return false; } });
  const page = {
    mainFrame() { return mainFrame; },
    frames() { return [mainFrame, ariaHiddenFrame, layoutHiddenFrame]; },
  };

  assert.strictEqual(await getAliyunFeedback(page), null);
});

test('Aliyun feedback prefers an explicit error over captcha across frames', async () => {
  const captchaFrame = fakeCaptchaFrame({
    '#nocaptcha.nc-container': captchaElement(),
  });
  const errorFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '用户名或密码错误，还可以重试3次 RequestId：private-request-id',
    }),
  });
  const page = {
    mainFrame() { return captchaFrame; },
    frames() { return [captchaFrame, errorFrame]; },
  };

  assert.deepStrictEqual(await getAliyunFeedback(page), { kind: 'password_rejected' });
});

test('Aliyun feedback prefers a hard credential error over an unknown error across frames', async () => {
  const unknownFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({ textContent: '当前登录状态无法继续' }),
  });
  const passwordFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({ textContent: '用户名或密码错误，还可以重试3次' }),
  });
  const page = {
    mainFrame() { return unknownFrame; },
    frames() { return [unknownFrame, passwordFrame]; },
  };

  assert.deepStrictEqual(await getAliyunFeedback(page), { kind: 'password_rejected' });
});

test('Aliyun feedback prefers captcha over an unknown error across frames', async () => {
  const unknownFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '当前登录状态无法继续',
    }),
  });
  const captchaFrame = fakeCaptchaFrame({
    '#nocaptcha.nc-container': captchaElement(),
  });
  const page = {
    mainFrame() {
      return unknownFrame;
    },
    frames() {
      return [unknownFrame, captchaFrame];
    },
  };

  assert.deepStrictEqual(await getAliyunFeedback(page), { kind: 'captcha' });
});

test('frame feedback scan continues after evaluate failure and logs only a safe debug summary', async () => {
  const failedFrame = {
    async evaluate() {
      throw new Error(`frame execution closed unexpectedly username=alice@example.com password=secret pwd=hidden token=token cookie=session csrf=csrf totp=123456 RequestId:abc <html>full DOM</html>${'x'.repeat(300)}`);
    },
  };
  const feedbackFrame = fakeCaptchaFrame({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '用户名或密码错误，还可以重试4次 RequestId: abc-123',
    }),
  });
  const page = {
    frames() {
      return [failedFrame, feedbackFrame];
    },
  };

  const debugLogs = await captureConsoleLogs(async () => {
    const feedback = await getAliyunFeedback(page, { debug: true });
    assert.deepStrictEqual(feedback, { kind: 'password_rejected' });
  });
  const normalLogs = await captureConsoleLogs(async () => {
    await getAliyunFeedback(page, { debug: false });
  });

  const debugOutput = debugLogs.join('\n');
  assert.match(debugOutput, /frame feedback scan failed: Error/);
  assert.doesNotMatch(debugOutput, /frame execution closed|username|alice@example.com|password|secret|pwd|hidden|token|cookie|csrf|totp|123456|RequestId|html|DOM/i);
  assert.ok(debugOutput.length <= 220);
  assert.strictEqual(normalLogs.join('\n'), '');
});

test('frame feedback scan ignores known navigation errors even in debug mode', async () => {
  const page = {
    frames() {
      return [{
        async evaluate() {
          throw new Error('Execution context was destroyed, most likely because of a navigation');
        },
      }];
    },
  };

  const debugLogs = await captureConsoleLogs(async () => {
    assert.strictEqual(await getAliyunFeedback(page, { debug: true }), null);
  });
  assert.strictEqual(debugLogs.join('\n'), '');
});

test('ordinary totp security code page is not captcha', () => {
  assert.strictEqual(detectCaptcha({
    'input[name="verifyCode"]': captchaElement({ textContent: '请输入 6 位数字安全码' }),
  }), false);
});

test('Aliyun feedback detects the visible password rejection beside the login form and ignores the MFA notice', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-notice': captchaElement({
      textContent: '为了更好地保护您的账户及资产安全，登录时强制进行 MFA 多因素认证',
    }),
    '[role="alert"].next-message-error': captchaElement({
      textContent: '用户名或密码错误，还可以重试3次 RequestId：private-request-id',
    }),
  });

  assert.deepStrictEqual(feedback, { kind: 'password_rejected' });
});

test('Aliyun feedback reads the active TOTP error and ignores a hidden passkey tab error', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': [
      captchaElement({ hiddenByAria: true, textContent: '用户名或密码错误，还可以重试3次' }),
      captchaElement({ textContent: '安全码错误。查看原因 RequestId：private-request-id' }),
    ],
  });

  assert.deepStrictEqual(feedback, { kind: 'totp_rejected' });
});

test('Aliyun feedback ignores notice-only pages and prefers an explicit error over same-page captcha', () => {
  assert.strictEqual(detectAliyunFeedback({
    '[role="alert"].next-message-notice': captchaElement({ textContent: '强制进行 MFA 多因素认证' }),
  }), null);

  assert.deepStrictEqual(detectAliyunFeedback({
    '[role="alert"].next-message-error': captchaElement({ textContent: '安全码错误。' }),
    '#nocaptcha.nc-container': captchaElement(),
  }), { kind: 'totp_rejected' });
});

test('Aliyun feedback prefers a hard credential error over an unknown same-page alert', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': [
      captchaElement({ textContent: '当前登录状态无法继续' }),
      captchaElement({ textContent: '安全码错误。' }),
    ],
  });

  assert.deepStrictEqual(feedback, { kind: 'totp_rejected' });
});

test('Aliyun feedback prefers captcha over an unknown visible error on the same page', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '当前登录状态无法继续',
    }),
    '#nocaptcha.nc-container': captchaElement(),
  });

  assert.deepStrictEqual(feedback, { kind: 'captcha' });
});

test('Aliyun feedback returns only a stable category for an unknown visible error', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '登录失败 RequestId: abc-123，请稍后重试',
    }),
  });

  assert.deepStrictEqual(feedback, { kind: 'login_feedback_unrecognized' });
});

test('Aliyun feedback ignores a hidden stale alert and reads the visible current alert', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': [
      captchaElement({ visible: false, textContent: '安全码错误。RequestId：stale' }),
      captchaElement({ textContent: '用户名或密码错误，还可以重试4次 RequestId：current' }),
    ],
  });

  assert.deepStrictEqual(feedback, { kind: 'password_rejected' });
});

test('Aliyun feedback detects a visible TOTP rejection alert without returning RequestId', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '安全码错误。查看原因 RequestId：abc-123',
    }),
  });

  assert.deepStrictEqual(feedback, { kind: 'totp_rejected' });
});

test('Aliyun feedback treats an unknown visible login error alert as terminal', () => {
  const feedback = detectAliyunFeedback({
    '[role="alert"].next-message-error': captchaElement({
      textContent: '当前登录状态无法继续，请稍后再试',
    }),
  });

  assert.deepStrictEqual(feedback, { kind: 'login_feedback_unrecognized' });
});

test('Aliyun auto-login actions keep optional password and MFA UI transitions but omit passkey verification', () => {
  assert.deepStrictEqual(autoLoginActionForState('password-choice'), {
    action: 'password-mode',
    wait: 'ui',
    expected: ['password'],
  });
  assert.deepStrictEqual(autoLoginActionForState('virtual-mfa'), {
    action: 'virtual-mfa',
    wait: 'ui',
    expected: ['totp'],
  });
  assert.deepStrictEqual(autoLoginActionForState('password'), {
    action: 'password-submit',
    wait: 'network',
    expected: ['virtual-mfa', 'totp', 'sls-console'],
  });
  assert.strictEqual(autoLoginActionForState('start-verify'), null);
});

test('Aliyun auto-login default pacing chooser stays within every inclusive operation range', () => {
  for (const operation of ['credential-fill', 'password-mode', 'virtual-mfa', 'next', 'password-submit', 'totp-submit']) {
    const [minimum, maximum] = autoLoginPacingRange(operation);
    for (let sample = 0; sample < 20; sample += 1) {
      const delay = chooseAliyunAutoLoginDelay(minimum, maximum);
      assert.strictEqual(Number.isInteger(delay), true);
      assert.ok(delay >= minimum && delay <= maximum, `${operation} delay ${delay} outside ${minimum}-${maximum}`);
    }
  }
});

test('Aliyun auto-login state machine follows optional password and MFA states once', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const pacingCalls = [];
    const delays = [401, 1001, 402, 403, 1002, 404, 405, 801];
    const page = fakeAliyunLoginPage('username', {
      next: 'password-choice',
      'password-mode': 'password',
      'password-submit': 'virtual-mfa',
      'virtual-mfa': 'totp',
      'totp-submit': 'sls-console',
    });
    page.advanceTime = advanceTime;

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'pw',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
      delayChooser: (operation, minimum, maximum) => {
        pacingCalls.push([operation, minimum, maximum]);
        return delays.shift();
      },
    });

    assert.deepStrictEqual(page.actions, ['next', 'password-mode', 'password-submit', 'virtual-mfa', 'totp-submit']);
    assert.deepStrictEqual(page.username.fills, ['alice@example.com']);
    assert.deepStrictEqual(page.password.fills, ['pw']);
    assert.strictEqual(page.totp.fills.length, 1);
    assert.deepStrictEqual(pacingCalls, [
      ['credential-fill', 400, 800],
      ['next', 1000, 2000],
      ['password-mode', 400, 800],
      ['credential-fill', 400, 800],
      ['password-submit', 1000, 2000],
      ['virtual-mfa', 400, 800],
      ['credential-fill', 400, 800],
      ['totp-submit', 800, 1000],
    ]);
    assert.deepStrictEqual(page.waits, [401, 1001, 500, 402, 500, 403, 1002, 500, 404, 500, 405, 801, 500]);
  });
});

test('Aliyun auto-login debug pacing output stays concise and redacted', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', { 'password-submit': 'sls-console' });
    page.advanceTime = advanceTime;

    const debugLogs = await captureConsoleLogs(() => runAliyunLoginAutomation(
      page,
      keychainArgs({ timeout: 10, debug: true }),
      {
        autoFillPlan: {
          username: 'alice@example.com',
          password: 'private-password',
          totpSeed: 'JBSWY3DPEHPK3PXP',
        },
        delayChooser: (operation) => operation === 'credential-fill' ? 400 : 1000,
      },
    ));

    const output = debugLogs.join('\n');
    assert.match(output, /auto-login pacing operation=credential-fill delay_ms=400 elapsed_ms=0/);
    assert.match(output, /auto-login pacing operation=password-submit delay_ms=1000 elapsed_ms=400/);
    assert.doesNotMatch(output, /alice@example\.com|private-password|JBSWY3DPEHPK3PXP|cookie|csrf|RequestId|https?:\/\//i);
  });
});

test('Aliyun auto-login treats SLS reached during a read-only feedback scan as normal success', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('username', {});
    const originalEvaluate = page.evaluate.bind(page);
    const originalUrl = page.url.bind(page);
    let reachedSls = false;
    page.advanceTime = advanceTime;
    page.url = () => reachedSls
      ? 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store'
      : originalUrl();
    page.evaluate = async (...call) => {
      const result = await originalEvaluate(...call);
      reachedSls = true;
      return result;
    };

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
      delayChooser: () => 400,
    });

    assert.deepStrictEqual(page.username.fills, []);
    assert.deepStrictEqual(page.actions, []);
  });
});

test('Aliyun auto-login rejects a foreign origin before scanning or changing its DOM', async () => {
  const calls = {
    frames: 0,
    locator: 0,
    role: 0,
    text: 0,
  };
  const page = {
    url() {
      return 'https://signin.aliyun.com.evil.example/login';
    },
    frames() {
      calls.frames += 1;
      return [this];
    },
    locator() {
      calls.locator += 1;
      return fakeInput('');
    },
    getByRole() {
      calls.role += 1;
      return fakeInput('');
    },
    getByText() {
      calls.text += 1;
      return fakeInput('');
    },
    async waitForTimeout() {
    },
  };

  await assert.rejects(
    runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
    }),
    { message: 'Aliyun auto-login stopped: foreign_origin' },
  );
  assert.deepStrictEqual(calls, {
    frames: 0,
    locator: 0,
    role: 0,
    text: 0,
  });
});

test('Aliyun auto-login accepts the account origin and enters the normal login state machine', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', { 'password-submit': 'sls-console' });
    const originalUrl = page.url.bind(page);
    page.url = () => {
      const currentUrl = originalUrl();
      return currentUrl.startsWith('https://sls.console.aliyun.com/')
        ? currentUrl
        : 'https://account.aliyun.com/login';
    };
    page.advanceTime = advanceTime;

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
      delayChooser: (operation) => operation === 'credential-fill' ? 400 : 1000,
    });

    assert.deepStrictEqual(page.password.fills, ['private-password']);
    assert.deepStrictEqual(page.actions, ['password-submit']);
  });
});

test('Aliyun auto-login accepts only the two exact HTTPS login origins', async () => {
  for (const currentUrl of [
    'http://signin.aliyun.com/login',
    'https://signin.aliyun.com:8443/login',
    'https://signin.aliyun.com.evil.example/login',
    'https://account.aliyun.com.evil.example/login',
    'https://example.com/login',
  ]) {
    let scanned = false;
    const page = {
      url() {
        return currentUrl;
      },
      frames() {
        scanned = true;
        return [this];
      },
      locator() {
        scanned = true;
        return fakeInput('');
      },
      async waitForTimeout() {
      },
    };

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: {
          username: 'alice@example.com',
          password: 'private-password',
          totpSeed: 'JBSWY3DPEHPK3PXP',
        },
      }),
      { message: 'Aliyun auto-login stopped: foreign_origin' },
    );
    assert.strictEqual(scanned, false, currentUrl);
  }
});

test('headed auto-fill stops on a foreign origin without scanning or changing its DOM', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const username = fakeInput('');
    const password = fakeInput('');
    const page = fakeLoginPage({
      '#loginName': username,
      '#loginPassword': password,
    }, {
      url: 'https://example.com/login',
      loggedInAfterWaits: Number.POSITIVE_INFINITY,
      advanceTime,
    });
    let locatorCalls = 0;
    let frameCalls = 0;
    const originalLocator = page.locator.bind(page);
    const originalFrames = page.frames.bind(page);
    page.locator = (selector) => {
      locatorCalls += 1;
      return originalLocator(selector);
    };
    page.frames = () => {
      frameCalls += 1;
      return originalFrames();
    };
    const notices = [];

    await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 1 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
      reportNotice: async (message) => {
        notices.push(message);
        throw new Error('notice unavailable');
      },
    });

    assert.strictEqual(locatorCalls, 0);
    assert.strictEqual(frameCalls, 0);
    assert.deepStrictEqual(username.fills, []);
    assert.deepStrictEqual(password.fills, []);
    assert.deepStrictEqual(page.injectedNotices, []);
    assert.deepStrictEqual(notices, [foreignOriginHandoffNotice]);
  });
});

test('headed auto-fill does not fill a credential after navigation leaves Aliyun', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const password = fakeInput('');
    const page = fakeLoginPage({
      '#loginPassword': password,
    }, {
      loggedInAfterWaits: Number.POSITIVE_INFINITY,
      advanceTime,
    });
    password.inputValue = async () => {
      page.setUrl('https://example.com/login');
      return '';
    };
    const notices = [];

    await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 1 }), {
      autoFillPlan: {
        username: 'alice@example.com',
        password: 'private-password',
        totpSeed: 'JBSWY3DPEHPK3PXP',
      },
      reportNotice: async (message) => notices.push(message),
    });

    assert.deepStrictEqual(password.fills, []);
    assert.deepStrictEqual(page.injectedNotices, []);
    assert.deepStrictEqual(notices, [foreignOriginHandoffNotice]);
  });
});

for (const [name, selector, plan, now] of [
  [
    'username',
    '#loginName',
    { username: 'alice@example.com', password: 'private-password', totpSeed: 'JBSWY3DPEHPK3PXP' },
    1000,
  ],
  [
    'totp',
    'input[placeholder="请输入 6 位数字安全码"]',
    { username: 'alice@example.com', password: 'private-password', totpSeed: 'JBSWY3DPEHPK3PXP' },
    31000,
  ],
]) {
  test(`headed auto-fill blocks ${name} mutation on a foreign navigation and reports one handoff`, async () => {
    await withFakeNow(now, async (advanceTime) => {
      const input = fakeInput('');
      const page = fakeLoginPage({
        [selector]: input,
      }, {
        loggedInAfterWaits: Number.POSITIVE_INFINITY,
        advanceTime,
      });
      input.inputValue = async () => {
        page.setUrl('https://example.com/login');
        return '';
      };
      const notices = [];

      await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 1 }), {
        autoFillPlan: plan,
        reportNotice: async (message) => notices.push(message),
      });

      assert.deepStrictEqual(input.fills, []);
      assert.deepStrictEqual(page.injectedNotices, []);
      assert.deepStrictEqual(notices, [foreignOriginHandoffNotice]);
    });
  });
}

test('headed auto-fill does not inject guidance after navigation reaches SLS or foreign', async () => {
  for (const [targetUrl, expectedNotices] of [
    ['https://sls.console.aliyun.com/lognext/project/proj/logsearch/store', []],
    ['https://example.com/login', [foreignOriginHandoffNotice]],
  ]) {
    await withFakeNow(1000, async (advanceTime) => {
      const page = fakeLoginPage({}, {
        loggedInAfterWaits: Number.POSITIVE_INFINITY,
        advanceTime,
      });
      const originalUrl = page.url.bind(page);
      let urlReads = 0;
      page.url = () => {
        urlReads += 1;
        return urlReads === 1 ? originalUrl() : targetUrl;
      };
      const notices = [];

      await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 1 }), {
        autoFillPlan: {
          username: '',
          password: null,
          totpSeed: null,
          totpUnsupported: false,
        },
        reportNotice: async (message) => notices.push(message),
      });

      assert.deepStrictEqual(page.injectedNotices, []);
      assert.deepStrictEqual(notices, expectedNotices);
    });
  }
});

for (const [stateName, inputName, now] of [
  ['username', 'username', 1000],
  ['password', 'password', 1000],
  ['totp', 'totp', 31000],
]) {
  test(`Aliyun auto-login blocks ${stateName} fill when navigation turns foreign at the mutation boundary`, async () => {
    await withFakeNow(now, async (advanceTime) => {
      const page = fakeAliyunLoginPage(stateName, {});
      const originalUrl = page.url.bind(page);
      let urlReads = 0;
      page.advanceTime = advanceTime;
      page.url = () => {
        urlReads += 1;
        return urlReads >= 3 ? 'https://example.com/login' : originalUrl();
      };

      await assert.rejects(
        runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
          autoFillPlan: {
            username: 'alice@example.com',
            password: 'private-password',
            totpSeed: 'JBSWY3DPEHPK3PXP',
          },
          delayChooser: () => 400,
        }),
        { message: 'Aliyun auto-login stopped: foreign_origin' },
      );

      assert.deepStrictEqual(page[inputName].fills, []);
    });
  });
}

test('Aliyun auto-login treats SLS reached at fill and click boundaries as normal success', async () => {
  for (const mutation of ['fill', 'click']) {
    await withFakeNow(1000, async (advanceTime) => {
      const page = fakeAliyunLoginPage('password', {});
      const originalUrl = page.url.bind(page);
      let urlReads = 0;
      page.advanceTime = advanceTime;
      if (mutation === 'click') page.password.value = 'manual-password';
      page.url = () => {
        urlReads += 1;
        return urlReads >= 3
          ? 'https://sls.console.aliyun.com/lognext/project/proj/logsearch/store'
          : originalUrl();
      };

      await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: {
          username: 'alice@example.com',
          password: 'private-password',
          totpSeed: 'JBSWY3DPEHPK3PXP',
        },
        delayChooser: () => 400,
      });

      assert.deepStrictEqual(page.password.fills, []);
      assert.deepStrictEqual(page.actions, []);
    });
  }
});

test('Aliyun auto-login does not click after navigation leaves Aliyun', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', {
      'password-submit': 'sls-console',
    });
    page.advanceTime = advanceTime;
    const originalUrl = page.url.bind(page);
    const originalGetByRole = page.getByRole.bind(page);
    let foreignOrigin = false;
    let clickCount = 0;
    page.url = () => foreignOrigin ? 'https://example.com/login' : originalUrl();
    page.getByRole = (role, options) => {
      const locator = originalGetByRole(role, options);
      return {
        first() {
          return this;
        },
        async isVisible(settings) {
          const visible = await locator.isVisible(settings);
          foreignOrigin = true;
          return visible;
        },
        async click(settings) {
          clickCount += 1;
          return locator.click(settings);
        },
      };
    };

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: {
          username: 'alice@example.com',
          password: 'private-password',
          totpSeed: 'JBSWY3DPEHPK3PXP',
        },
        delayChooser: () => 400,
      }),
      { message: 'Aliyun auto-login stopped: foreign_origin' },
    );

    assert.strictEqual(clickCount, 0);
  });
});

test('Aliyun auto-login discards stale fill and click operations after pacing waits', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const staleFillPage = fakeAliyunLoginPage('username', {
      __afterWait: ['password'],
      'password-submit': 'sls-console',
    });
    staleFillPage.advanceTime = advanceTime;

    await runAliyunLoginAutomation(staleFillPage, keychainArgs({ timeout: 10 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      delayChooser: () => 400,
    });

    assert.deepStrictEqual(staleFillPage.username.fills, []);
    assert.deepStrictEqual(staleFillPage.password.fills, ['pw']);
    assert.deepStrictEqual(staleFillPage.actions, ['password-submit']);

    const staleClickPage = fakeAliyunLoginPage('username', {
      __afterWait: [null, 'password'],
      'password-submit': 'sls-console',
    });
    staleClickPage.advanceTime = advanceTime;

    await runAliyunLoginAutomation(staleClickPage, keychainArgs({ timeout: 10 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      delayChooser: () => 400,
    });

    assert.deepStrictEqual(staleClickPage.username.fills, ['alice@example.com']);
    assert.deepStrictEqual(staleClickPage.actions, ['password-submit']);
  });
});

for (const [initialState, feedbackState, errorKind] of [
  ['username', 'captcha', 'captcha'],
  ['password', 'password-rejected', 'password_rejected'],
  ['totp', 'totp-rejected', 'totp_rejected'],
]) {
  test(`Aliyun auto-login stops on ${errorKind} feedback after credential-fill pacing without a stale action`, async () => {
    await withFakeNow(1000, async (advanceTime) => {
      const page = fakeAliyunLoginPage(initialState, { __afterWait: feedbackState });
      page.advanceTime = advanceTime;

      await assert.rejects(
        runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
          autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
          delayChooser: () => 400,
        }),
        new RegExp(errorKind),
      );

      assert.deepStrictEqual(page.username.fills, []);
      assert.deepStrictEqual(page.password.fills, []);
      assert.deepStrictEqual(page.totp.fills, []);
      assert.deepStrictEqual(page.actions, []);
      assert.deepStrictEqual(page.waits, [400]);
    });
  });
}

test('Aliyun auto-login generates TOTP after its fill delay and renews within six seconds', async () => {
  await withFakeNow(23900, async (advanceTime) => {
    const page = fakeAliyunLoginPage('totp', { 'totp-submit': 'sls-console' });
    page.advanceTime = advanceTime;

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      delayChooser: (operation) => operation === 'credential-fill' ? 800 : 900,
    });

    assert.deepStrictEqual(page.totp.fillTimes, [31700]);
    assert.deepStrictEqual(page.totp.fills, ['996554']);
    assert.deepStrictEqual(page.waits, [800, 7000, 900, 500]);
  });
});

test('auto-fill does not use the auto-login pacing chooser', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeLoginPage({}, { loggedInAfterWaits: 1, advanceTime });

    await runAliyunAutoFillMonitor(page, keychainArgs({ timeout: 2 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      delayChooser: () => {
        throw new Error('auto-fill must not use auto-login pacing');
      },
    });

    assert.deepStrictEqual(page.waitDurations, [500]);
  });
});

test('Aliyun auto-login keeps polling transient unknown after TOTP submission until SLS console', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('totp', {
      'totp-submit': 'unknown',
      __onWait: ['unknown', 'sls-console'],
    });
    page.advanceTime = advanceTime;

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      delayChooser: (operation) => operation === 'totp-submit' ? 800 : 400,
    });

    assert.deepStrictEqual(page.actions, ['totp-submit']);
    assert.deepStrictEqual(page.waits, [400, 800, 500, 500]);
    assert.deepStrictEqual(page.observedStates, ['totp', 'totp', 'totp', 'unknown']);
  });
});

test('Aliyun auto-login reports totp-submit timeout for persistent unknown state', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('totp', { 'totp-submit': 'unknown' });
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
        delayChooser: (operation) => operation === 'totp-submit' ? 800 : 400,
      }),
      /totp-submit_timeout/,
    );
    assert.deepStrictEqual(page.actions, ['totp-submit']);
    assert.deepStrictEqual(page.waits, [400, 800, 500, 500, 500, 500, 500, 500]);
  });
});

test('Aliyun auto-login state machine waits for the initial Aliyun page to render before acting', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('unknown', {
      __onWait: 'sls-console',
    });
    page.advanceTime = advanceTime;

    await runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
      autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
    });

    assert.deepStrictEqual(page.actions, []);
    assert.deepStrictEqual(page.waits, [500]);
  });
});

test('Aliyun auto-login initial render observation does not outlive the auth timeout', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('unknown', {});
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 1 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      }),
      /login_timeout/,
    );
    assert.deepStrictEqual(page.actions, []);
    assert.deepStrictEqual(page.waits, [500, 500]);
  });
});

test('Aliyun auto-login state machine stops immediately when password rejection appears', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', { 'password-submit': 'password-rejected' });
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
        delayChooser: (operation) => operation === 'password-submit' ? 1000 : 400,
      }),
      /password_rejected/,
    );
    assert.deepStrictEqual(page.actions, ['password-submit']);
    assert.deepStrictEqual(page.waits, [400, 1000, 500]);
  });
});

for (const [initialState, submitAction, hardState, hardKind] of [
  ['password', 'password-submit', 'password-rejected', 'password_rejected'],
  ['totp', 'totp-submit', 'totp-rejected', 'totp_rejected'],
]) {
  test(`Aliyun auto-login waits past transient captcha for ${hardKind} without retrying the submission`, async () => {
    await withFakeNow(1000, async (advanceTime) => {
      const page = fakeAliyunLoginPage(initialState, {
        [submitAction]: 'captcha',
        __afterWait: [null, null, null, hardState],
      });
      page.advanceTime = advanceTime;
      page.once = () => {};
      page.off = () => {};
      page.isClosed = () => false;
      const context = {
        pages() { return [page]; },
        once() {},
        on() {},
        browser() { return null; },
      };
      const restarts = [];

      await assert.rejects(
        captureAuthWithBrowser({ context }, keychainArgs({ timeout: 10 }), {
          username: 'alice@example.com',
          password: 'pw',
          totpSeed: 'JBSWY3DPEHPK3PXP',
        }, { automationMode: 'auto-login', browserMode: 'headless' }, {
          captureSlsAuth: async (capturedPage, capturedContext, capturedArgs, { abortSignal }) => new Promise((resolve, reject) => {
            abortSignal.addEventListener('abort', () => reject(abortSignal.reason), { once: true });
          }),
          openLoginPage: async () => {},
          restartAliyunLoginFlow: async () => { restarts.push('restart'); },
        }),
        new RegExp(hardKind),
      );

      assert.deepStrictEqual(page.actions, [submitAction]);
      assert.deepStrictEqual(restarts, []);
    });
  });
}

test('Aliyun auto-login returns persistent post-submit captcha at the existing transition deadline', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', { 'password-submit': 'captcha' });
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
        delayChooser: (operation) => operation === 'password-submit' ? 1000 : 400,
      }),
      /Aliyun auto-login stopped: captcha/,
    );

    assert.deepStrictEqual(page.actions, ['password-submit']);
    assert.strictEqual(page.waits.filter((milliseconds) => milliseconds === 500).length, 6);
  });
});

test('Aliyun auto-login debug output keeps only the stable feedback category', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const debugPage = fakeAliyunLoginPage('password', { 'password-submit': 'password-rejected' });
    debugPage.advanceTime = advanceTime;
    const debugLogs = await captureConsoleLogs(() => assert.rejects(
      runAliyunLoginAutomation(debugPage, keychainArgs({ timeout: 10, debug: true }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      }),
      /password_rejected/,
    ));

    const normalPage = fakeAliyunLoginPage('password', { 'password-submit': 'password-rejected' });
    normalPage.advanceTime = advanceTime;
    const normalLogs = await captureConsoleLogs(() => assert.rejects(
      runAliyunLoginAutomation(normalPage, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      }),
      /password_rejected/,
    ));

    assert.match(debugLogs.join('\n'), /auto-login feedback: password_rejected/);
    assert.doesNotMatch(debugLogs.join('\n'), /用户名|密码错误|RequestId/i);
    assert.doesNotMatch(normalLogs.join('\n'), /用户名|密码错误|RequestId/i);
  });
});

test('Aliyun auto-login feedback scan forwards debug mode after a failed frame evaluation', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const failedFrame = {
      async evaluate() {
        throw new Error('password=secret Cookie=session RequestId:abc <html>full DOM</html>');
      },
    };
    const page = fakeAliyunLoginPage('password', { 'password-submit': 'password-rejected' });
    page.advanceTime = advanceTime;
    page.frames = () => [failedFrame, page];

    const debugLogs = await captureConsoleLogs(() => assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10, debug: true }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      }),
      /password_rejected/,
    ));

    assert.match(debugLogs.join('\n'), /frame feedback scan failed/);
    assert.doesNotMatch(debugLogs.join('\n'), /secret|Cookie|RequestId|full DOM/i);
  });
});

test('Aliyun auto-login captcha feedback keeps a compact debug category', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('captcha', {});
    page.advanceTime = advanceTime;
    const debugLogs = await captureConsoleLogs(() => assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10, debug: true }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
      }),
      /Aliyun auto-login stopped: captcha/,
    ));

    assert.match(debugLogs.join('\n'), /auto-login feedback: captcha/);
  });
});

for (const [state, errorKind] of [
  ['totp', 'totp_rejected'],
  ['captcha', 'captcha'],
  ['unknown-rejected', 'login_feedback_unrecognized'],
]) {
  test(`Aliyun auto-login state machine stops immediately on ${errorKind}`, async () => {
    await withFakeNow(1000, async (advanceTime) => {
      const transitions = state === 'totp' ? { 'totp-submit': 'totp-rejected' } : {};
      const page = fakeAliyunLoginPage(state, transitions);
      page.advanceTime = advanceTime;

      await assert.rejects(
        runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
          autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
          delayChooser: (operation) => operation === 'totp-submit' ? 800 : 400,
        }),
        new RegExp(errorKind),
      );
      assert.strictEqual(page.actions.length, state === 'totp' ? 1 : 0);
      assert.deepStrictEqual(page.waits, state === 'totp' ? [400, 800, 500] : []);
    });
  });
}

test('Aliyun auto-login state machine limits a submission transition to 3 seconds', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password', {});
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
        delayChooser: (operation) => operation === 'password-submit' ? 1000 : 400,
      }),
      /password-submit_timeout/,
    );
    assert.deepStrictEqual(page.actions, ['password-submit']);
    assert.deepStrictEqual(page.waits, [400, 1000, 500, 500, 500, 500, 500, 500]);
  });
});

test('Aliyun auto-login state machine limits a UI transition to one observation', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeAliyunLoginPage('password-choice', {});
    page.advanceTime = advanceTime;

    await assert.rejects(
      runAliyunLoginAutomation(page, keychainArgs({ timeout: 10 }), {
        autoFillPlan: { username: 'alice@example.com', password: 'pw', totpSeed: 'JBSWY3DPEHPK3PXP' },
        delayChooser: () => 400,
      }),
      /password-mode_timeout/,
    );
    assert.deepStrictEqual(page.actions, ['password-mode']);
    assert.deepStrictEqual(page.waits, [400, 500]);
  });
});
