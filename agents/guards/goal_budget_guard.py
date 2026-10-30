#!/usr/bin/env python3

import json,sys

def decision(payload):
    return {}

if __name__=='__main__':
    try: payload=json.load(sys.stdin)
    except (ValueError,TypeError): payload={}
    print(json.dumps(decision(payload),ensure_ascii=False))
