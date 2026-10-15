#!/usr/bin/env python3
"""Prevent unconfigured default AWS identity for literal mall SSM commands."""
import json,re,sys

def extract_strings(obj):
 if isinstance(obj,dict):
  return [s for value in obj.values() for s in extract_strings(value)]
 if isinstance(obj,list):return [s for value in obj for s in extract_strings(value)]
 return [obj] if isinstance(obj,str) else []

def reject(payload):
 for text in extract_strings(payload.get('tool_input',payload)):
  normalized=re.sub(r"['\",]",' ',text)
  for part in re.split(r'[;&\n|]+',normalized):
   matches=list(re.finditer(r'\baws\s+',part))
   for i,match in enumerate(matches):
    end=matches[i+1].start() if i+1<len(matches) else len(part)
    args=part[match.end():end]
    if not re.search(r'\bssm\b',args):continue
    known_mall=any(x in args for x in ['i-084ca75f70f1aaac9','i-05717da94e8d052bf'])
    if not ('ap-east-2' in args or known_mall):continue
    profile=re.search(r'--profile(?:\s*=\s*|\s+)([^\s\)]+)',args)
    if profile:
     if profile.group(1)=='mall' or not known_mall:continue
     return True
    environment=re.search(r'\bAWS_PROFILE\s*=\s*([A-Za-z0-9_.-]+)(?:\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*[A-Za-z0-9_.-]+)*\s*$',part[:match.start()])
    if environment:
     assignments=re.findall(r'\bAWS_PROFILE\s*=\s*([A-Za-z0-9_.-]+)',environment.group(0))
     if assignments and (assignments[-1]=='mall' or not known_mall):continue
    return True
 return False

def main():
 try:payload=json.load(sys.stdin)
 except (ValueError,TypeError):return 0
 if not isinstance(payload,dict):return 0
 if reject(payload):
  print('SSM操作須明確指定身分；已核定的商城主機須使用商城身分，不使用預設身分。',file=sys.stderr)
  return 2
 return 0
if __name__=='__main__':raise SystemExit(main())
