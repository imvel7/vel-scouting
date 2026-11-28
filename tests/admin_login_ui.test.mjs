// Tests for the login message and role label helpers inside admin.html.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(root, 'admin.html'), 'utf8');
const start = html.indexOf('// LOGIN-UI-START');
const end = html.indexOf('// LOGIN-UI-END');
assert.ok(start > 0 && end > start, 'login ui markers present');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(html.slice(start, end) + '\nthis.api={roleLabel,loginErrorText,dashboardAccessText};', ctx);
const { roleLabel, loginErrorText, dashboardAccessText } = ctx.api;

test('role labels', () => {
  assert.equal(roleLabel('admin'), 'Yönetici');
  assert.equal(roleLabel('editor'), 'Editör');
  assert.equal(roleLabel('x'), 'Bilinmeyen rol');
  assert.equal(roleLabel(null), 'Bilinmeyen rol');
});
test('dashboard text shows the real role, never a fixed admin claim', () => {
  assert.ok(dashboardAccessText('editor').includes('Editör'));
  assert.ok(!dashboardAccessText('editor').includes('Yönetici'));
  assert.ok(dashboardAccessText('admin').includes('Yönetici'));
});
test('login errors are translated', () => {
  assert.match(loginErrorText({ message: 'Invalid login credentials' }), /hatalı/);
  assert.match(loginErrorText({ message: 'Email not confirmed' }), /onaylanmamış/);
  assert.match(loginErrorText({ message: 'email rate limit exceeded' }), /Çok fazla/);
  assert.match(loginErrorText({ message: 'TypeError: Failed to fetch' }), /Bağlantı/);
});
test('unknown or missing errors fall back safely', () => {
  assert.equal(loginErrorText({ message: 'Bu hesapta Vel Scouting yönetim yetkisi bulunmuyor.' }), 'Bu hesapta Vel Scouting yönetim yetkisi bulunmuyor.');
  assert.match(loginErrorText(null), /Giriş başarısız/);
  assert.match(loginErrorText({}), /Giriş başarısız/);
});
