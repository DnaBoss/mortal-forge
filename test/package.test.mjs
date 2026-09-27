import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
test('real tarball installs through npm and survives npm package removal', t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'mortal-pack-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 function run(cmd,args,env={}){const r=spawnSync(cmd,args,{encoding:'utf8',timeout:60000,env:{...process.env,...env}});assert.equal(r.status,0,r.stderr||r.stdout);return r.stdout;}
 const packed=JSON.parse(run('npm',['pack','--json','--pack-destination',dir]));
 assert.ok(packed[0].files.some(f=>f.path==='.agents/skills/mortal-tools/SKILL.md'));
 const prefix=path.join(dir,'prefix'),home=path.join(dir,'home');
 run('npm',['install','--global','--prefix',prefix,'--ignore-scripts','--no-audit','--no-fund',path.join(dir,packed[0].filename)]);
 const bin=path.join(prefix,'bin/mortal-tools');run(bin,['install'],{MORTAL_HOME:home});
 run('npm',['uninstall','--global','--prefix',prefix,'--ignore-scripts','mortal-dev-tools']);
 const stable=path.join(home,'.local/share/mortal-tools/package/bin/mortal-tools.mjs');
 run(process.execPath,[stable,'install'],{MORTAL_HOME:home});
 run(process.execPath,[stable,'uninstall'],{MORTAL_HOME:home});
});
