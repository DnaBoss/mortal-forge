'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const POLICY = path.join(__dirname, 'POLICY.md');
const RULES = [
  {term: /\bTCN\b/iu, explanation: /連續.{0,8}(走勢|時間|資料)|時間卷積|時序卷積/u, hint: '能讀連續走勢的模型'},
  {term: /驗證窗/gu, explanation: /測試.{0,10}(日期|期間|時段)|日期.{0,10}測試/u, hint: '拿來測試的那段日期'},
  {term: /凍結模型/gu, explanation: /固定版本|不再修改|停止更新/u, hint: '固定模型版本，測試期間不再修改'},
  {term: /\bholdout\b/giu, explanation: /保留.{0,12}測試|未.{0,6}訓練/u, hint: '保留作測試、未拿來訓練的資料'},
  {term: /\bbuckets?\b/giu, explanation: /觀察點|時間格|時間區間/u, hint: '依實際長度寫成幾秒觀察點'}
];

function inspect(text) {
  if (typeof text !== 'string' || !text.trim()) return ['沒有可檢查的回答'];
  // Fenced executable material and exact block quotes are not prose.
  // Inline backticks do not exempt terminology.
  const prose = text.replace(/```[^\n]*\n[\s\S]*?```|~~~[^\n]*\n[\s\S]*?~~~/g, '')
    .replace(/^\s*>.*$/gm, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
  const failures = [];
  for (const sentence of prose.split(/[。！？\n]/u)) {
    for (const rule of RULES) {
      rule.term.lastIndex = 0;
      if (rule.term.test(sentence) && !rule.explanation.test(sentence)) failures.push(rule.hint);
    }
  }
  return [...new Set(failures)];
}

function audit(event, accepted, count) {
  // Store no prompt, reply, transcript, working-directory or credential data.
  const dir = path.join(__dirname, 'audit');
  fs.mkdirSync(dir, {recursive: true, mode: 0o700});
  fs.appendFileSync(path.join(dir, 'events.jsonl'), JSON.stringify({
    at: new Date().toISOString(), event, accepted, violations: count,
    policy: crypto.createHash('sha256').update(fs.readFileSync(POLICY)).digest('hex')
  }) + '\n', {mode: 0o600});
}

function hook(input) {
  const name = input.hook_event_name;
  // Not on UserPromptSubmit: CLAUDE.md / AGENTS.md already carry the policy, so
  // repeating it every prompt only grows the context.
  if (['SessionStart', 'PostCompact', 'SubagentStart'].includes(name)) {
    const policy = fs.readFileSync(POLICY, 'utf8');
    audit(name, true, 0);
    return {hookSpecificOutput: {hookEventName: name, additionalContext: policy}};
  }
  if (name !== 'Stop') return {};
  const failures = inspect(input.last_assistant_message);
  audit(name, failures.length === 0, failures.length);
  if (!failures.length) return {};
  if (input.stop_hook_active) {
    // Do not create an unbounded model-call loop. This does not retract text
    // already streamed by the host; the buffered gate is the output boundary.
    return {continue: false, stopReason: '白話檢查仍未通過，已停止自動重寫。',
      systemMessage: '這次回答未通過白話檢查，不能標為合格。'};
  }
  // The rules travel with the hook: Claude Code no longer carries POLICY.md in
  // CLAUDE.md (2026-10-03), so the full policy is attached at the moment of failure.
  return {decision: 'block', reason: '白話檢查未通過。只重寫剛才的回答，不執行工具或重做任務。'
    + '請用以下說法或在同一句解釋原名：' + failures.join('；') + '。保留學習曲線等常用詞。\n\n'
    + fs.readFileSync(POLICY, 'utf8')};
}

function main() {
  const mode = process.argv[2] || 'hook';
  try {
    const raw = fs.readFileSync(0, 'utf8');
    if (mode === 'gate' || mode === 'check') {
      const failures = inspect(raw);
      audit(mode, !failures.length, failures.length);
      if (failures.length) {
        process.stderr.write('白話檢查未通過：' + failures.join('；') + '\n');
        process.exitCode = 2;
      } else if (mode === 'gate') process.stdout.write(raw);
      else process.stdout.write(JSON.stringify({accepted: true}) + '\n');
      return;
    }
    if (mode !== 'hook') throw new Error('Unknown guard mode');
    process.stdout.write(JSON.stringify(hook(JSON.parse(raw))) + '\n');
  } catch {
    // Never echo unvalidated input on failure.
    process.stderr.write('白話檢查程式失敗，沒有放行回答。\n');
    process.exitCode = 2;
  }
}

module.exports = {inspect, hook};
if (require.main === module) main();
