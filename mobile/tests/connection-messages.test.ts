import assert from 'node:assert/strict';
import test from 'node:test';

import {
  connectionTitle,
  describeAnalysisFailure,
  describeHealthFailure,
  HEALTH_RETRY_DELAYS_MS,
  kindFromStatus,
  nextHealthRetryDelay,
  type FailureKind,
} from '../src/lib/connection-messages.ts';

const kinds: FailureKind[] = ['network', 'timeout', 'auth', 'server', 'unexpected', 'not-petlens'];

test('no message mentions a laptop, Wi-Fi, or internal detail', () => {
  for (const kind of kinds) {
    assert.doesNotMatch(describeHealthFailure(kind), /laptop|wi-?fi|localhost|stack|exception/i);
  }
  assert.doesNotMatch(describeAnalysisFailure({ kind: 'network' }, 60), /laptop|wi-?fi/i);
});

test('network failure uses the device-neutral wording', () => {
  assert.equal(describeHealthFailure('network'), 'Unable to connect. Check your internet connection and try again.');
  assert.equal(connectionTitle('network'), 'Offline');
  assert.equal(connectionTitle('server'), 'Server unavailable');
});

test('HTTP statuses map to failure kinds', () => {
  assert.equal(kindFromStatus(401), 'auth');
  assert.equal(kindFromStatus(503), 'server');
  assert.equal(kindFromStatus(404), 'unexpected');
});

test('automatic retries are bounded', () => {
  assert.equal(nextHealthRetryDelay(0), HEALTH_RETRY_DELAYS_MS[0]);
  assert.equal(nextHealthRetryDelay(HEALTH_RETRY_DELAYS_MS.length), null);
  assert.equal(nextHealthRetryDelay(1000), null);
});

test('analysis failures never leak server internals on 5xx', () => {
  const text = describeAnalysisFailure({ kind: 'http', status: 500, serverMessage: 'Traceback: db password' }, 60);
  assert.doesNotMatch(text, /Traceback|password/);
});

test('analysis failures keep a helpful 4xx message and the size limit', () => {
  assert.equal(describeAnalysisFailure({ kind: 'http', status: 400, serverMessage: 'Clip is too short.' }, 60), 'Clip is too short.');
  assert.match(describeAnalysisFailure({ kind: 'http', status: 413, serverMessage: '' }, 60), /60 MB/);
  assert.equal(describeAnalysisFailure({ kind: 'cancelled' }, 60), 'Analysis was cancelled.');
});
