import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const cli=path.resolve('bin/mortal-tools.mjs');
function fixture(t){const h=fs.mkdtempSync(path.join(os.tmpdir(),'mortal-install-'));t.after(()=>fs.rmSync(h,{recursive:true,force:true}));return h;}
function run(home,...args){return spawnSync(process.execPath,[cli,...args],{env:{...process.env,MORTAL_HOME:home},encoding:'utf8'});}
test('install/update/uninstall preserve existing rules and stable payload works',t=>{
 const h=fixture(t), rules=path.join(h,'.codex/AGENTS.md');fs.mkdirSync(path.dirname(rules),{recursive:true});fs.writeFileSync(rules,'Keep my original rule\n');
 for(const cmd of ['install','install','update'])assert.equal(run(h,cmd).status,0);
 assert.equal((fs.readFileSync(rules,'utf8').match(/mortal-tools:start/g)||[]).length,1);
 const stable=path.join(h,'.local/share/mortal-tools/package/bin/mortal-tools.mjs');
 assert.equal(spawnSync(process.execPath,[stable,'install'],{env:{...process.env,MORTAL_HOME:h}}).status,0);
 assert.equal(run(h,'uninstall').status,0);
 assert.equal(fs.readFileSync(rules,'utf8'),'Keep my original rule\n\n');
 assert.equal(run(h,'uninstall').status,0);
});
test('edited skill rejects update and uninstall without altering rules',t=>{
 const h=fixture(t);assert.equal(run(h,'install').status,0);
 const p=path.join(h,'.agents/skills/mortal-tools/SKILL.md');fs.appendFileSync(p,'local change');
 const r=path.join(h,'.codex/AGENTS.md'),before=fs.readFileSync(r,'utf8');
 assert.equal(run(h,'update').status,1);assert.equal(run(h,'uninstall').status,1);assert.equal(fs.readFileSync(r,'utf8'),before);
});
test('unowned skill rejected before any managed rules are written',t=>{
 const h=fixture(t),p=path.join(h,'.claude/skills/mortal-tools/SKILL.md');fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'mine');
 assert.equal(run(h,'install').status,1);assert.equal(fs.existsSync(path.join(h,'.codex/AGENTS.md')),false);
});
test('repo init idempotent and altered block is preserved',t=>{
 const h=fixture(t);fs.mkdirSync(path.join(h,'.git'));const p=path.join(h,'AGENTS.md');fs.writeFileSync(p,'original\n');
 assert.equal(run(h,'init',h).status,0);assert.equal(run(h,'init',h).status,0);
 for (const rel of ['CLAUDE.md','GEMINI.md','.cursor/rules/mortal-tools.mdc','.windsurf/rules/mortal-tools.md','.github/copilot-instructions.md'])
  assert.match(fs.readFileSync(path.join(h,rel),'utf8'),/mortal-tools:start/);
 assert.equal(run(h,'uninit',h).status,0);assert.equal(fs.readFileSync(p,'utf8'),'original\n\n');
 for (const rel of ['CLAUDE.md','GEMINI.md','.cursor/rules/mortal-tools.mdc','.windsurf/rules/mortal-tools.md','.github/copilot-instructions.md'])
  assert.equal(fs.readFileSync(path.join(h,rel),'utf8'),'');
 assert.equal(run(h,'init',h).status,0);fs.writeFileSync(p,fs.readFileSync(p,'utf8').replace('共用工具','my rule'));
 assert.equal(run(h,'uninit',h).status,1);assert.match(fs.readFileSync(p,'utf8'),/my rule/);
});
