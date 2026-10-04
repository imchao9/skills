#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { grantDingTalkLocalNetworkAccess } = require('../auth-login');

test('CRP auth preauthorizes DingTalk local network access without making it required', async () => {
  const calls = [];
  assert.equal(await grantDingTalkLocalNetworkAccess({
    grantPermissions: async (...args) => calls.push(args),
  }), true);
  assert.deepEqual(calls, [[['local-network-access'], { origin: 'https://login.dingtalk.com' }]]);
  assert.equal(await grantDingTalkLocalNetworkAccess({
    grantPermissions: async () => { throw new Error('unsupported'); },
  }), false);
});
