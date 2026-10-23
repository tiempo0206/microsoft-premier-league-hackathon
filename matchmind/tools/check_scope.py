"""Report owned-path violations. Run from matchmind after changes are staged/committed."""
import argparse,subprocess,sys
p=argparse.ArgumentParser(); p.add_argument('--role',choices=['A','B','C'],required=True); p.add_argument('--base',default='HEAD'); a=p.parse_args()
prefixes={'A':['frontend/','tests/frontend/','docs/handoff/frontend.md'],'B':['backend/','data/generator/','data/extra/','tests/backend/','deploy/','docs/handoff/backend.md'],'C':['ai/','evaluation/','tests/ai/','docs/handoff/ai.md']}
# git paths are made relative to current matchmind directory. Untracked files are included.
def run(args): return subprocess.check_output(['git',*args],text=True).splitlines()
paths=set(run(['diff','--name-only','--relative',a.base,'--','.'])+run(['ls-files','--others','--exclude-standard','--','.']))
bad=[x for x in sorted(paths) if not any(x==q or x.startswith(q) for q in prefixes[a.role])]
if bad: print('OUTSIDE ROLE SCOPE: '+', '.join(bad)); sys.exit(1)
print('Role scope OK; still inspect the full diff and exclude unrelated pre-existing changes.')
