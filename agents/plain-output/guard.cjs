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

const LENGTH_LIMIT = 600; // prose characters per reply (user 2026-10-15); code blocks excluded
const FULL_REQUEST = /完整|詳細|全部|原文|逐條|逐項|一個一個|說明/u;

function proseOf(text) {
  return text.replace(/```[^\n]*\n[\s\S]*?```|~~~[^\n]*\n[\s\S]*?~~~/g, '')
    .replace(/^\s*>.*$/gm, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
}

function tooLong(text, prompt) {
  if (typeof text !== 'string') return false;
  if (typeof prompt === 'string' && FULL_REQUEST.test(prompt)) return false;
  return proseOf(text).replace(/\s+/g, '').length > LENGTH_LIMIT;
}

function lastUserPrompt(transcriptPath) {
  // Read only the tail of the transcript; the last typed prompt is near the end.
  try {
    const fd = fs.openSync(transcriptPath, 'r');
    try {
      const size = fs.fstatSync(fd).size;
      const length = Math.min(size, 4 * 1024 * 1024);
      const buffer = Buffer.alloc(length);
      fs.readSync(fd, buffer, 0, length, size - length);
      const lines = buffer.toString('utf8').split('\n');
      for (let i = lines.length - 1; i >= 0; i--) {
        if (!lines[i].includes('"type":"user"')) continue;
        let record;
        try { record = JSON.parse(lines[i]); } catch { continue; }
        if (record.type !== 'user' || record.isCompactSummary || record.isMeta) continue;
        const content = record.message && record.message.content;
        if (typeof content === 'string') return content;
        if (Array.isArray(content) && content.every(c => c && c.type === 'text')) {
          return content.map(c => c.text || '').join('\n');
        }
      }
    } finally { fs.closeSync(fd); }
  } catch { /* no transcript: treat as no exemption */ }
  return '';
}

function inspect(text) {
  if (typeof text !== 'string' || !text.trim()) return ['沒有可檢查的回答'];
  // Fenced executable material and exact block quotes are not prose.
  // Inline backticks do not exempt terminology.
  const prose = proseOf(text);
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
  if (tooLong(input.last_assistant_message, lastUserPrompt(input.transcript_path))) {
    failures.push(`回覆超過 ${LENGTH_LIMIT} 字元（不含程式碼）。只留結論、原因、下一步各一兩句；`
      + '使用者要完整內容時會說「完整」或「詳細」');
  }
  audit(name, failures.length === 0, failures.length);
  if (!failures.length) return {};
  if (input.stop_hook_active) {
    // Do not create an unbounded model-call loop. This does not retract text
    // already streamed by the host; the buffered gate is the output boundary.
    return {continue: false, stopReason: '白話檢查仍未通過，已停止自動重寫。',
      systemMessage: '這次回答未通過白話檢查，不能標為合格。'};
  }
  // The user sees this text (2026-10-15: "why dump the rules, just rewrite"), so it carries
  // only what failed; the full policy stays in POLICY.md for the model to read when needed.
  return {decision: 'block', reason: '白話檢查未通過：' + failures.join('；')
    + '。只重寫剛才的回答；規則在 ' + POLICY + '。'};
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

module.exports = {inspect, hook, tooLong, lastUserPrompt, LENGTH_LIMIT};
if (require.main === module) main();
