import hashlib,json,subprocess,sys,unittest.mock as mock
from pathlib import Path
sys.path.insert(0,"/home/cash/.agents/guards")
import write_guard as g
root=Path("/home/cash/.agents/evidence/evidence-json-key-20261004")
base="/home/cash/.agents/evidence/fluke-evidence-read-20261004"
load="d=json.loads((p/'v2-manual-hook-evidence.json').read_text());"
def cmd(body): return "python3 - <<'PY'\nimport pathlib,json\np=pathlib.Path("+repr(base)+");"+body+"\nPY"
rows=[]
for name,body,expected in [
("missing",load+"print(d['cases'])",True),
("valid",load+"print(d['manual_cases'])",False),
("alias_mutation",load+"e=d;e.update({'cases':[]});print(d['cases'])",False),
("keyword_mutation",load+"mutate=lambda data:data.update({'cases':[]});mutate(data=d);print(d['cases'])",False),
("same_statement_mutation",load+"mutate=lambda data:data.update({'cases':[]});print(mutate(d),d['cases'])",False),
("direct_assignment",load+"d['cases']=[];print(d['cases'])",False),
("nested",load+"print(d['manual_cases'][0]['cases'])",False),
("unknown_function",load+"mutate(d);print(d['cases'])",False),
("module_attribute_rebind","json.loads=other;"+load+"print(d['cases'])",False),
("path_attribute_rebind","pathlib.Path=other;p=pathlib.Path("+repr(base)+");"+load+"print(d['cases'])",False),
]:
 payload={"tool_name":"exec_command","tool_input":{"cmd":cmd(body),"workdir":"/home/cash/orca/workspaces/Fluke/riichi-finetune"}}
 result=g.verdict(payload)[0]
 rows.append(dict(name=name,payload=payload,expected_deny=expected,rule=result,matched=(result=='evidence-json-key')==expected))
actual=[]
for row in rows[2:5]:
 source=row['payload']['tool_input']['cmd'].split("\n",1)[1].rsplit("\nPY",1)[0]
 proc=subprocess.run([sys.executable,"-c",source],capture_output=True,text=True,timeout=5)
 actual.append(dict(name=row['name'],exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
manual=[]
for row in rows[:2]:
 proc=subprocess.run([sys.executable,"/home/cash/.agents/guards/write_guard.py"],input=json.dumps(row['payload']),capture_output=True,text=True,timeout=5)
 manual.append(dict(name=row['name'],exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
# Mock filesystem boundaries to avoid creating files or symlinks outside review scope.
bounds=[]
for name,real,size,content,expected in [
("symlink_outside","/tmp/outside.json",2,"{}",False),
("outside_prefix_collision","/home/cash/.agents/evidence-other/x.json",2,"{}",False),
("large_object",base+"/v2-manual-hook-evidence.json",1048577,"{}",False),
("nonobject",base+"/v2-manual-hook-evidence.json",2,"[]",False),
("malformed",base+"/v2-manual-hook-evidence.json",1,"{",False),
]:
 orig=g.os.path.realpath
 target=base+"/v2-manual-hook-evidence.json"
 with mock.patch.object(g.os.path,'realpath',side_effect=lambda x: real if str(x)==target else orig(x)),mock.patch.object(g.os.path,'getsize',return_value=size),mock.patch('builtins.open',mock.mock_open(read_data=content)):
  found=g.missing_fluke_evidence_read(cmd(load+"print(d['cases'])"),'/home/cash',json_keys=True)
 bounds.append(dict(name=name,denied=found,matched=found==expected))
long=cmd(load+"print(d['cases'])")+'#'*65537
bounds.append(dict(name='command_limit',denied=g.missing_fluke_evidence_read(long,'/home/cash',json_keys=True)))
# Real repeated recognized reads are bounded; the 17th known missing read is not inspected.
body=''.join("d%d=json.loads((p/'v2-manual-hook-evidence.json').read_text());"%i for i in range(17))+"print(d16['cases'])"
bounds.append(dict(name='read_limit_17',denied=g.missing_fluke_evidence_read(cmd(body),'/home/cash',json_keys=True)))
out={'schema':'independent-json-key-review-v1','guard_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'semantic_cases':rows,'manual_hook_only':manual,'actual_read_only_counterexample_execution':actual,'boundary_cases':bounds,'host_automatic_integration_verified':False,'usage_source':'unavailable'}
(root/'independent-review-cases.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'semantic_cases':len(rows),'mismatches':[r['name'] for r in rows if not r['matched']],'boundaries':bounds},indent=2))
