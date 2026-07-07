const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const test = require('node:test');

const skillRoot = path.resolve(__dirname, '..', '..');
const skillctl = path.join(skillRoot, 'scripts', 'skillctl');
const {
  REDACTED,
  redactText,
  redactValue,
} = require('../skillctl');

function runCli(args, options = {}) {
  return spawnSync(skillctl, args, {
    cwd: skillRoot,
    encoding: 'utf8',
    input: options.input || '',
  });
}

test('skillctl credential seal reads plaintext from stdin and prints sealed value only', () => {
  const result = runCli(['credential', 'seal'], { input: 'secret-password' });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout.trim(), /^sealed:v1:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$/);
  assert.doesNotMatch(result.stdout, /secret-password/);
  assert.equal(result.stderr, '');
});

test('skillctl credential check validates sealed values without revealing plaintext', () => {
  const seal = runCli(['credential', 'seal'], { input: 'secret-password' });
  const result = runCli(['credential', 'check'], { input: seal.stdout });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /credential ok/);
  assert.doesNotMatch(result.stdout, /secret-password/);
});

test('skillctl does not provide credential reveal', () => {
  const result = runCli(['credential', 'reveal'], { input: 'sealed:v1:a:b:c' });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unsupported_command/);
  assert.doesNotMatch(result.stdout, /secret/);
});

test('skillctl setup check verifies installable dependencies without auth checks', () => {
  const result = runCli(['setup', '--check']);

  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /\[ok\] node/);
  assert.match(result.stdout, /\[ok\] npm/);
  assert.match(result.stdout, /\[ok\] package-lock\.json/);
  assert.match(result.stdout, /\[ok\] mysql2/);
  assert.match(result.stdout, /\[ok\] redis/);
  assert.match(result.stdout, /\[ok\] mongodb/);
  assert.match(result.stdout, /\[ok\] playwright/);
  assert.match(result.stdout, /\[ok\] chrome/);
  assert.doesNotMatch(result.stdout, /alilog auth/);
  assert.doesNotMatch(result.stdout, /dbops/);
});

test('skillctl redactText masks mobile numbers and sensitive key values', () => {
  const text = [
    'mobile=13812345678',
    'password=plain-secret',
    'Authorization: Bearer abc.def',
    '"accessKeySecret":"ak-secret"',
    'cookie=sessionid=abc; path=/',
  ].join('\n');

  const redacted = redactText(text);

  assert.match(redacted, /138\*\*\*\*5678/);
  assert.doesNotMatch(redacted, /13812345678|plain-secret|abc\.def|ak-secret|sessionid=abc/);
  assert.match(redacted, /password=<redacted>/);
  assert.match(redacted, /Authorization: <redacted>/i);
  assert.match(redacted, /"accessKeySecret":"<redacted>"/);
  assert.match(redacted, /cookie=<redacted>/);
});

test('skillctl redaction leaves already-redacted values stable', () => {
  const text = [
    'mobile=138****5678',
    'password=<redacted>',
    'token=[redacted]',
    'redis.password=sealed:v1:abc:def:ghi',
  ].join('\n');

  assert.equal(redactText(text), text);
});

test('skillctl redactValue recursively redacts without throwing on unusual values', () => {
  const input = {
    phone: '13911112222',
    nested: {
      token: 'secret-token',
      ok: 'traceId=abc',
    },
    rows: [
      { mobile: '13700001111', value: 'keep' },
    ],
  };
  input.self = input;

  assert.doesNotThrow(() => redactValue(input));
  const redacted = redactValue(input);

  assert.equal(redacted.phone, '139****2222');
  assert.equal(redacted.nested.token, REDACTED);
  assert.equal(redacted.nested.ok, 'traceId=abc');
  assert.equal(redacted.rows[0].mobile, '137****1111');
  assert.equal(redacted.rows[0].value, 'keep');
  assert.equal(redacted.self, '[Circular]');
});
