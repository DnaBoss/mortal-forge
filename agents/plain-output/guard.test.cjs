'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const {inspect, hook} = require('./guard.cjs');

test('common wording is preserved', () => {
  assert.deepEqual(inspect('學習曲線上升，勝率提高，停損維持相同設定。'), []);
});
test('unexplained examples are rejected', () => {
  assert.equal(inspect('用 TCN 跑驗證窗，再凍結模型。').length, 3);
});
test('inline code cannot hide jargon', () => {
  assert.equal(inspect('採用 `TCN`。').length, 1);
});
test('necessary terminology with explanation passes', () => {
  assert.deepEqual(inspect('TCN 是能讀連續走勢的模型。'), []);
});
test('explanation in another sentence does not exempt a term', () => {
  assert.equal(inspect('TCN 有改善。這是一種能讀連續走勢的模型。').length, 1);
});
test('code and exact quotes are not silently changed', () => {
  assert.deepEqual(inspect('命令如下：\n```sh\necho TCN\n```\n> TCN'), []);
});
test('hook requests one rewrite', () => {
  assert.equal(hook({hook_event_name: 'Stop', last_assistant_message: 'TCN 更好。'}).decision, 'block');
});
test('repeated failure stops and reports failure', () => {
  const result = hook({hook_event_name: 'Stop', last_assistant_message: 'TCN 更好。', stop_hook_active: true});
  assert.equal(result.continue, false);
  assert.match(result.systemMessage, /未通過/);
});
test('missing answer is not silently accepted', () => {
  assert.equal(hook({hook_event_name: 'Stop'}).decision, 'block');
});
test('policy is added at session start', () => {
  const result = hook({hook_event_name: 'SessionStart'});
  assert.match(result.hookSpecificOutput.additionalContext, /學習曲線/);
});
test('policy is not repeated on every user prompt', () => {
  assert.deepEqual(hook({hook_event_name: 'UserPromptSubmit'}), {});
});
test('buffered gate exposes zero answer bytes on violation', () => {
  const result = spawnSync(process.execPath, [path.join(__dirname, 'guard.cjs'), 'gate'], {input: 'TCN 更好。', encoding: 'utf8'});
  assert.equal(result.status, 2);
  assert.equal(result.stdout, '');
});
test('buffered gate preserves acceptable answer exactly', () => {
  const text = '學習曲線持續改善。\n';
  const result = spawnSync(process.execPath, [path.join(__dirname, 'guard.cjs'), 'gate'], {input: text, encoding: 'utf8'});
  assert.equal(result.status, 0);
  assert.equal(result.stdout, text);
});
test('invalid hook input is an explicit failure', () => {
  const result = spawnSync(process.execPath, [path.join(__dirname, 'guard.cjs'), 'hook'], {input: '{', encoding: 'utf8'});
  assert.equal(result.status, 2);
  assert.equal(result.stdout, '');
});
