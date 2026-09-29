'use strict';

const {spawn, spawnSync} = require('node:child_process');
const path = require('node:path');

function answerFrom(engine, raw) {
  if (engine === 'claude') {
    const result = JSON.parse(raw);
    if (result.is_error || result.subtype !== 'success' || typeof result.result !== 'string') throw Error('Provider failed');
    return result.result;
  }
  if (engine !== 'codex') throw Error('Unknown provider');
  let answer = null, completed = false;
  for (const line of raw.split('\n').filter(s => s.trim())) {
    const event = JSON.parse(line);
    if (event.type === 'turn.failed' || event.type === 'error') throw Error('Provider failed');
    if (event.type === 'turn.completed') completed = true;
    if (event.type === 'item.completed' && event.item?.type === 'agent_message') {
      answer = event.item.text;
    }
  }
  if (!completed || typeof answer !== 'string') throw Error('Incomplete answer');
  return answer;
}

function main() {
  const [engine, ...words] = process.argv.slice(2);
  if (!['codex', 'claude'].includes(engine) || !words.length) {
    process.stderr.write('用法：plain-ai codex "問題" 或 plain-ai claude "問題"\n');
    process.exitCode = 2; return;
  }
  const prompt = words.join(' ');
  // Answer-oriented entry point: Codex uses its read-only sandbox;
  // Claude has no tools. This is not a replacement for coding sessions.
  const args = engine === 'codex'
    ? ['exec', '--json', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only', prompt]
    : ['-p', '--output-format', 'json', '--no-session-persistence', '--tools', '', prompt];
  const child = spawn('/home/cash/.local/bin/' + engine, args, {stdio: ['ignore', 'pipe', 'pipe']});
  let raw = '', bytes = 0, failed = false;
  const timer = setTimeout(() => {failed = true; child.kill('SIGTERM');}, 120000);
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', chunk => {
    bytes += Buffer.byteLength(chunk, 'utf8');
    if (bytes > 16 * 1024 * 1024) {failed = true; child.kill('SIGTERM'); return;}
    raw += chunk;
  });
  // Provider diagnostics may contain partial unvalidated prose. Do not render.
  child.stderr.on('data', () => {});
  child.on('error', () => {failed = true;});
  child.on('close', code => {
    clearTimeout(timer);
    try {
      if (failed || code !== 0) throw Error('Provider failed');
      const answer = answerFrom(engine, raw);
      const gate = spawnSync(process.execPath, [path.join(__dirname, 'guard.cjs'), 'gate'], {
        input: answer, encoding: 'utf8', timeout: 5000, maxBuffer: 16 * 1024 * 1024
      });
      if (gate.status !== 0) {
        process.stderr.write('回答未通過白話檢查，已攔下，沒有顯示原文。\n');
        process.exitCode = 2; return;
      }
      process.stdout.write(gate.stdout + (gate.stdout.endsWith('\n') ? '' : '\n'));
    } catch {
      process.stderr.write('這次未取得可通過檢查的完整回答，沒有顯示原文。\n');
      process.exitCode = 2;
    }
  });
}

module.exports = {answerFrom};
if (require.main === module) main();
