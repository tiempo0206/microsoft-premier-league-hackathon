import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
expected=json.loads((ROOT/'contracts/frozen.sha256.json').read_text(encoding='utf-8'))
failures=[]
for name,digest in expected.items():
    p=ROOT/name
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest: failures.append(name)
if failures: print('CONTRACT CHANGE NEEDS REVIEW: '+', '.join(failures)); sys.exit(1)
print('Frozen contracts and fixtures unchanged')
