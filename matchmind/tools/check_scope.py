"""Report owned-path violations. Run from matchmind after changes are staged/committed."""
import argparse,subprocess,sys
p=argparse.ArgumentParser(); p.add_argument('--role',choices=['A','B','C'],required=True); p.add_argument('--base',default='HEAD'); a=p.parse_args()
# The C entry also carries the ownership the role card gives the integrator: root
# configuration (TEAM_ROLES.json, the file C1 exists to fill in), the shared root tests,
# and tools/ itself — the card assigns tools/ to the integrator, and this guard has to be
# listed to be editable at all. A guard cannot meaningfully guard itself; the human diff
# review below is what covers that.
# contracts/ and data/fixtures/ are deliberately NOT listed: editing a frozen contract
# must stay a two-step, reviewed decision rather than a scope check that silently passes.
prefixes={'A':['frontend/','tests/frontend/','docs/handoff/frontend.md'],
          'B':['backend/','data/generator/','data/extra/','tests/backend/','deploy/','docs/handoff/backend.md'],
          'C':['ai/','evaluation/','tests/ai/','docs/handoff/ai.md','TEAM_ROLES.json',
               'tests/test_contracts.py','tests/test_mock_api.py','tools/','.gitignore']}
# git paths are made relative to current matchmind directory. Untracked files are included.
def run(args): return subprocess.check_output(['git',*args],text=True).splitlines()
paths=set(run(['diff','--name-only','--relative',a.base,'--','.'])+run(['ls-files','--others','--exclude-standard','--','.']))
bad=[x for x in sorted(paths) if not any(x==q or x.startswith(q) for q in prefixes[a.role])]
if bad: print('OUTSIDE ROLE SCOPE: '+', '.join(bad)); sys.exit(1)
print('Role scope OK; still inspect the full diff and exclude unrelated pre-existing changes.')
