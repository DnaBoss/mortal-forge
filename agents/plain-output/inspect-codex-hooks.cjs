'use strict';
// Read-only local protocol inspection. No model turn or network probe is sent.
const {spawn} = require('node:child_process');
const child = spawn('/home/cash/.local/bin/codex', ['app-server', '--stdio'], {stdio: ['pipe', 'pipe', 'pipe']});
let buffer = '';
const timer = setTimeout(() => {child.kill(); process.exitCode = 1;}, 15000);
const send = (obj) => child.stdin.write(JSON.stringify(obj) + '\n');
child.stderr.on('data', () => {});
child.stdout.on('data', data => {
  buffer += data.toString();
  let index;
  while ((index = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, index); buffer = buffer.slice(index + 1);
    let message;
    try {message = JSON.parse(line);} catch {continue;}
    if (message.id === 1) {
      if (message.error) {console.error(JSON.stringify(message.error)); child.kill(); continue;}
      send({method: 'initialized', params: {}});
      send({id: 2, method: 'hooks/list', params: {cwds: ['/home/cash']}});
    }
    if (message.id === 2) {
      console.log(JSON.stringify(message));
      clearTimeout(timer); child.kill();
    }
  }
});
child.on('exit', () => clearTimeout(timer));
send({id: 1, method: 'initialize', params: {clientInfo: {name: 'plain_style_check', version: '1.0'}, capabilities: {experimentalApi: true}}});
