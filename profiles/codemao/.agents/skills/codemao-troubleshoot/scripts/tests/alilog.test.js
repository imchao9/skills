#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const EventEmitter = require('node:events');
const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const test = require('node:test');
const {
  parseArgs,
  parseTime,
  parseTimeExpression,
  buildQueryBody,
  buildLogstoresRequest,
  normalizeResult,
  isSuccessfulQueryOutput,
  extractPayloadLogs,
  formatQueryOutput,
  formatFieldsOutput,
  formatLogstoresOutput,
  detectAliyunCaptchaInDocument,
  loginAutoFillGuidanceMessage,
  shouldInjectLoginGuidanceNotice,
  openLoginPage,
  reportAutoFillFailure,
  autoLoginAliyun,
  hasAliyunCaptcha,
  fetchWithTimeout,
  captureSlsAuth,
  installBrowserAuthCloseHandlers,
  formatAuthSuccessOutput,
  applyUserConfig,
  readUsernameFromKeychainAccount,
  readPasswordFromKeychain,
  readTotpSeedFromKeychain,
} = require('../alilog');

const longContent = `${'a'.repeat(1300)}continued tail`;
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

function assertThrowsMessage(fn, pattern) {
  assert.throws(fn, (error) => pattern.test(error.message));
}

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
      if (name === 'href') return this.href;
      if (name === 'src') return this.src;
      return '';
    },
    ...extra,
  };
}

function captchaDocument(elementsBySelector) {
  return {
    querySelector(selector) {
      return elementsBySelector[selector] || null;
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

test('autoLoginAliyun corrects initial non-empty username once', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun keeps manual username edits after same-url navigation', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun refills non-first empty username after 1s only', async () => {
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

      await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun keeps manual username edits after url changes', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun fills password even after user changes username', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun fills password when username input is not on the current page', async () => {
  const oldPassword = process.env.ALILOG_PASSWORD;
  process.env.ALILOG_PASSWORD = 'pw';
  try {
    const password = fakeInput('');
    const page = fakeLoginPage({
      '#loginPassword': password,
    });

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun keeps password and totp empty-field fill rules with username mismatch', async () => {
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

      await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun does not fill local totp into phone code input', async () => {
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

      await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun does not fill local totp into ambiguous otp field', async () => {
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

      await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun restarts login flow immediately on captcha without filling fields', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun does not inject guidance on non-login blank page', async () => {
  await withFakeNow(1000, async (advanceTime) => {
    const page = fakeLoginPage({}, {
      url: 'about:blank',
      loggedInAfterWaits: 2,
      advanceTime,
    });

    await autoLoginAliyun(page, keychainArgs({
      username: '',
      timeout: 4,
      debug: false,
      totpInputSelector: '',
    }));

    assert.deepStrictEqual(page.injectedNotices, []);
  });
});

test('autoLoginAliyun hands over to manual login when captcha restart leaves the browser blank', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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

test('autoLoginAliyun stops auto-fill and shows guidance notice after captcha limit', async () => {
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

    await autoLoginAliyun(page, keychainArgs({
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
    assert.doesNotMatch(page.injectedNoticeSources.at(-1), /translate\(-50%, -50%\)/);
  });
});

test('openLoginPage reports signin navigation failure', async () => {
  const page = {
    async goto() {
      throw new Error('network unavailable');
    },
  };

  await assert.rejects(
    () => openLoginPage(page, {}, keychainArgs()),
    /failed to open Aliyun login page: network unavailable/,
  );
});

test('reportAutoFillFailure only prints when auth debug is enabled', () => {
  const lines = [];
  const originalLog = console.log;
  console.log = (line) => lines.push(String(line));
  try {
    reportAutoFillFailure({ debug: false }, new Error('hidden failure'));
    assert.deepStrictEqual(lines, []);

    reportAutoFillFailure({ debug: true }, new Error('visible failure'));
    assert.deepStrictEqual(lines, ['auth: auto-fill failed: visible failure']);
  } finally {
    console.log = originalLog;
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

test('SLS docs keep alilog raw and tid guidance aligned with CLI contract', () => {
  const skillRoot = `${__dirname}/../..`;
  const skill = fs.readFileSync(`${skillRoot}/SKILL.md`, 'utf8');
  const sls = fs.readFileSync(`${skillRoot}/references/sls.md`, 'utf8');

  assert.match(skill, /执行工具命令时正常等待进程结束后再读取输出/);
  assert.match(sls, /SLS 查询不提供 raw/);
  assert.doesNotMatch(sls, /--raw/);
  assert.doesNotMatch(sls, /--extra-fields[^\n]*tid/);
  assert.match(sls, /TID 通常是正文文本，不是稳定字段名/);
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

test('alilog auth help exposes optional target hint parameters', () => {
  const script = `${__dirname}/../alilog`;
  const help = execFileSync(process.execPath, [script, 'auth', '--help'], { encoding: 'utf8' });

  assert.match(help, /alilog auth/);
  assert.match(help, /--project PROJECT/);
  assert.match(help, /--logstore LOGSTORE/);
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
    '--force-login',
    '--no-auto-fill',
    '--timeout', '300',
    '--debug',
  ]);
  assert.strictEqual(auth.forceLogin, true);
  assert.strictEqual(auth.noAutoFill, true);
  assert.strictEqual(auth.timeout, 300);
  assert.strictEqual(auth.debug, true);

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

test('applyUserConfig resolves username by explicit arg file then Keychain account', async () => {
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
});

test('auth success output is compact plain text', () => {
  const text = formatAuthSuccessOutput();

  assert.strictEqual(text, 'auth ready');
  assertThrowsMessage(() => JSON.parse(text), /Unexpected token|Unexpected end/);
  assert.doesNotMatch(text, /ok|msg|auth_file|generated_at/);
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

test('ordinary totp security code page is not captcha', () => {
  assert.strictEqual(detectCaptcha({
    'input[name="verifyCode"]': captchaElement({ textContent: '请输入 6 位数字安全码' }),
  }), false);
});
