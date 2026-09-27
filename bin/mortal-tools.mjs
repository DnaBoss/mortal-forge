#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const home = path.resolve(process.env.MORTAL_HOME || os.homedir());
const base = path.join(home, '.local/share/mortal-tools');
const manifestPath = path.join(base, 'install.json');
const begin = '<!-- mortal-tools:start -->', end = '<!-- mortal-tools:end -->';
const block = `${begin}\n共用工具：先讀 ~/.agents/skills/mortal-tools/SKILL.md；搜尋既有工具後再實作。簡單讀檔／搜尋直接 Shell，重複流程復用腳本，已有 MCP 操作依 SKILL 呼叫。不得重造已有工具；授權、模型成本與專案規則仍優先。\n${end}`;
const digest = s => createHash('sha256').update(s).digest('hex');
const read = p => fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
function write(p,s) { fs.mkdirSync(path.dirname(p),{recursive:true}); fs.writeFileSync(p,s); }
function section(s) {
 const a=s.indexOf(begin), b=s.indexOf(end);
 if (a<0 && b<0) return null;
 if (a<0 || b<a || s.indexOf(begin,a+1)>=0 || s.indexOf(end,b+1)>=0) throw Error('Malformed managed block');
 return s.slice(a,b+end.length);
}
function managed(p,remove=false) {
 const s=read(p), old=section(s);
 if(old && old!==block) throw Error(`Managed block was edited; preserve and inspect: ${p}`);
 if(remove) {
  if(!old) return s;
  if(s===old || s===old+'\n') return '';
  return s.replace(old,'');
 }
 return old ? s : s+(s && !s.endsWith('\n')?'\n':'')+block+'\n';
}
const targets = ['.agents/skills/mortal-tools/SKILL.md','.claude/skills/mortal-tools/SKILL.md'];
const rules = ['.codex/AGENTS.md','.claude/CLAUDE.md'];
const repoRuleFiles = ['AGENTS.md','CLAUDE.md','GEMINI.md','.cursor/rules/mortal-tools.mdc','.windsurf/rules/mortal-tools.md','.github/copilot-instructions.md'];
function install() {
 const prev=fs.existsSync(manifestPath)?JSON.parse(read(manifestPath)):null;
 const skill=read(path.join(source,'.agents/skills/mortal-tools/SKILL.md'));
 if(!skill) throw Error('Packaged SKILL missing');
 for(const r of targets) {
  const p=path.join(home,r);
  if(fs.existsSync(p) && (!prev || digest(read(p))!==prev.skillHash)) throw Error(`Unowned or edited skill: ${p}`);
 }
 const edits=rules.map(r=>[path.join(home,r),managed(path.join(home,r))]);
 // Preflight all conflicts before changing files. Stable payload survives npx cache cleanup.
 const payload=path.join(base,'package');
 if(path.resolve(source)!==payload) {
  fs.mkdirSync(payload,{recursive:true});
  for(const r of ['bin','.agents','server.py','call.py','pyproject.toml','uv.lock','package.json'])
   fs.cpSync(path.join(source,r),path.join(payload,r),{recursive:true});
 }
 for(const r of targets) write(path.join(home,r),skill);
 for(const [p,s] of edits) write(p,s);
 write(manifestPath,JSON.stringify({version:JSON.parse(read(path.join(source,'package.json'))).version,skillHash:digest(skill)},null,2));
 console.log(JSON.stringify({ok:true,installed:base,next:'mortal-tools doctor; mortal-tools connect',note:'Restart AI sessions to discover skills. Existing services unchanged.'}));
}
function uninstall() {
 if(!fs.existsSync(manifestPath)) {console.log('Not installed');return;}
 const m=JSON.parse(read(manifestPath));
 for(const r of targets) if(fs.existsSync(path.join(home,r)) && digest(read(path.join(home,r)))!==m.skillHash) throw Error(`Edited skill preserved: ${r}`);
 const edits=rules.map(r=>[path.join(home,r),managed(path.join(home,r),true)]);
 for(const [p,s] of edits) if(fs.existsSync(p)) write(p,s);
 for(const r of targets) if(fs.existsSync(path.join(home,r))) fs.unlinkSync(path.join(home,r));
 fs.unlinkSync(manifestPath);
 console.log('Removed managed skills/rules. Stable package, MCP registrations and running services preserved.');
}
async function doctor() {
 const checks={installed:fs.existsSync(manifestPath),skills:targets.every(r=>fs.existsSync(path.join(home,r))),rules:rules.every(r=>section(read(path.join(home,r)))===block)};
 for(const cmd of ['uv','python3']) checks[cmd]=spawnSync(cmd,['--version'],{timeout:5000,stdio:'ignore'}).status===0;
 try {
  const res=await fetch('http://127.0.0.1:18765/mcp',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json, text/event-stream'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'mortal-doctor',version:'0.1.0'}}}),signal:AbortSignal.timeout(4000)});
  const data=await res.json(); checks.mcp=res.ok && data.result?.serverInfo?.name==='mortal-mcp';
 } catch {checks.mcp=false;}
 console.log(JSON.stringify({ok:Object.values(checks).every(Boolean),checks,note:'MCP initialize is not gameplay acceptance; client skill loading requires a new session.'},null,2));
 if(!Object.values(checks).every(Boolean)) process.exitCode=1;
}
function run(args, service=false) {
 const result=spawnSync('uv',['run','--project',source,'--frozen','python',...args],{stdio:'inherit',...(service ? {} : {timeout:320000})});
 if(result.error) throw result.error;
 process.exitCode=result.status ?? 1;
}
try {
 const [command,...args]=process.argv.slice(2);
 if(['install','update'].includes(command)) install();
 else if(command==='uninstall') uninstall();
 else if(command==='doctor') await doctor();
 else if(['init','uninit'].includes(command)) {
  const repo=path.resolve(args[0] || process.cwd());
  if(!fs.existsSync(path.join(repo,'.git'))) throw Error('Expected repository root containing .git');
  const edits=repoRuleFiles.map(r=>[path.join(repo,r),managed(path.join(repo,r),command==='uninit')]);
  for(const [p,s] of edits) write(p,s);
  console.log(`${command}: ${repo}`);
 } else if(command==='connect') {
  console.log('codex mcp add mortal --url http://127.0.0.1:18765/mcp\nclaude mcp add --transport http --scope user mortal http://127.0.0.1:18765/mcp\nInspect existing registrations before running; this command does not overwrite client config.');
 } else if(command==='call') {
  if(!args[0] || !/^[a-z][a-z0-9_]*$/.test(args[0])) throw Error('Expected MCP tool name');
  run([path.join(source,'call.py'),...args]);
 } else if(command==='serve') run([path.join(source,'server.py')],true);
 else {console.log('mortal-tools install|update|doctor|connect|call <tool> [--arguments JSON]|serve|init [repo]|uninit [repo]|uninstall');if(command)process.exitCode=1;}
} catch(e) {console.error(e.message);process.exitCode=1;}
