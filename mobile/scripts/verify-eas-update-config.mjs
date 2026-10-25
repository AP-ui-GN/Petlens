import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const app = JSON.parse(await readFile(new URL('../app.json', import.meta.url), 'utf8')).expo;
const eas = JSON.parse(await readFile(new URL('../eas.json', import.meta.url), 'utf8'));
const pkg = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
const expectedUpdatesUrl = `https://u.expo.dev/${app.extra?.eas?.projectId}`;

assert.ok(app.extra?.eas?.projectId, 'EAS project ID must be configured');
assert.equal(app.updates?.enabled, true, 'EAS Updates must be enabled');
assert.equal(app.updates?.url, expectedUpdatesUrl, 'EAS Updates URL must match the existing project ID');
assert.equal(app.updates?.checkAutomatically, 'ON_LOAD', 'Updates must be checked on launch');
assert.equal(app.updates?.fallbackToCacheTimeout, 0, 'App startup must not wait for a network update check');
assert.deepEqual(app.runtimeVersion, { policy: 'fingerprint' }, 'Runtime version must track native compatibility');
assert.ok(pkg.dependencies?.['expo-updates'], 'expo-updates must be installed');
assert.equal(eas.build?.production?.channel, 'production', 'Production builds must use the production channel');
assert.equal(eas.build?.production?.android?.buildType, 'apk', 'Production Android builds must produce an APK');
assert.match(eas.build?.production?.env?.EXPO_PUBLIC_API_URL ?? '', /^https:\/\//, 'Production API URL must remain HTTPS');
assert.equal(eas.build?.preview?.channel, 'preview', 'Preview builds must use the preview channel');
assert.equal(eas.build?.development?.channel, 'development', 'Development builds must use the development channel');

console.log('EAS Update configuration is valid.');
console.log(`Project: ${app.extra.eas.projectId}`);
console.log(`Runtime policy: ${app.runtimeVersion.policy}`);
console.log(`Production channel: ${eas.build.production.channel} (APK)`);
console.log(`Preview channel: ${eas.build.preview.channel}`);
