// Address validation cases shared with the backend (backend/tests/test_url_inspection.py).
// Uses Node's built-in test runner and TypeScript type stripping: no extra packages.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { normalizeUrl, validationMessage } from '../src/lib/url.ts';

const cases = JSON.parse(readFileSync(new URL('../../tests/url_validation_cases.json', import.meta.url), 'utf8'));

test('accepted addresses and their normalised form', () => {
  for (const [input, normalized] of cases.accepted) {
    const result = normalizeUrl(input);
    assert.equal(result.ok ? result.url : result.error, normalized, JSON.stringify(input));
  }
});

test('rejected addresses and their error code', () => {
  for (const [code, inputs] of Object.entries(cases.rejected)) {
    for (const input of inputs) {
      const result = normalizeUrl(input);
      assert.equal(result.ok ? 'accepted' : result.error, code, JSON.stringify(input));
    }
  }
});

test('credential messages never repeat the input', () => {
  for (const input of cases.rejected.credentials_not_allowed) {
    const message = validationMessage(normalizeUrl(input));
    assert.match(message, /kabul edilmiyor/);
    assert.doesNotMatch(message, /password|p%40ss/);
  }
});

test('known differences: only the backend rejects these', () => {
  for (const [input] of cases.serverOnlyRejections) {
    assert.equal(normalizeUrl(input).ok, true, JSON.stringify(input));
  }
});
