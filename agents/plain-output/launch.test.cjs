'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {answerFrom} = require('./launch.cjs');

test('Codex returns final answer, not intermediate progress or tool output', () => {
  const events = [
    {type: 'item.completed', item: {type: 'agent_message', text: 'progress'}},
    {type: 'item.completed', item: {type: 'command_execution', aggregated_output: 'private'}},
    {type: 'item.completed', item: {type: 'agent_message', text: '完成。'}},
    {type: 'turn.completed'}
  ];
  assert.equal(answerFrom('codex', events.map(e => JSON.stringify(e)).join('\n')), '完成。');
});
test('Incomplete Codex stream fails closed', () => {
  assert.throws(() => answerFrom('codex', JSON.stringify({type: 'item.completed', item: {type: 'agent_message', text: 'partial'}})));
});
test('Claude provider failure is not an answer', () => {
  assert.throws(() => answerFrom('claude', JSON.stringify({is_error: true, subtype: 'success', result: 'error'})));
});
test('Claude successful answer is extracted', () => {
  assert.equal(answerFrom('claude', JSON.stringify({subtype: 'success', result: '學習曲線改善。'})), '學習曲線改善。');
});
test('Malformed provider output fails closed', () => {
  assert.throws(() => answerFrom('codex', 'not json'));
  assert.throws(() => answerFrom('claude', 'not json'));
});
