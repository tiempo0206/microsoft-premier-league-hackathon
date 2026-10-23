from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
defs=json.loads((ROOT/'contracts/contract.schema.json').read_text(encoding='utf-8'))['$defs']
def typ(s):
    if '$ref' in s: return s['$ref'].rsplit('/',1)[-1]
    if 'const' in s: return json.dumps(s['const'],ensure_ascii=False)
    if 'enum' in s: return ' | '.join(json.dumps(x) for x in s['enum'])
    for key in ('anyOf','oneOf'):
        if key in s: return '('+' | '.join(typ(x) for x in s[key])+')'
    t=s.get('type')
    if t=='object': return '{ '+ '; '.join(k+('' if k in s.get('required',[]) else '?')+': '+typ(v) for k,v in s['properties'].items())+' }'
    if t=='array': return 'Array<'+typ(s['items'])+'>'
    return {'string':'string','integer':'number','number':'number','boolean':'boolean','null':'null'}[t]
out='// GENERATED from contract.schema.json. Edit through a reviewed contract change only.\n'
out+='\n'.join('export type '+name+' = '+typ(value)+';' for name,value in defs.items())+'\n'
(ROOT/'contracts/types.ts').write_text(out,encoding='utf-8',newline='\n')
print('Generated contracts/types.ts')
