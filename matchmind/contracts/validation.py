"""Shared shape + cross-field checks. Do not label tactical causality as proven."""
from pathlib import Path
import json
from jsonschema import Draft202012Validator
SCHEMA=json.loads((Path(__file__).parent/'contract.schema.json').read_text(encoding='utf-8'))
def check_shape(name, value):
    Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':SCHEMA['$defs']}).validate(value)
def check_request(req):
    check_shape('AnalysisRequest',req)
    w=req['window']
    if w['start_sec']>w['end_sec']: raise ValueError('reversed window')
    ids=set()
    for e in req['events']:
        if e['match_id']!=req['match_id']: raise ValueError('wrong match')
        if not w['start_sec']<=e['timestamp_sec']<=w['end_sec']: raise ValueError('event outside window')
        if e['event_id'] in ids: raise ValueError('duplicate event id')
        ids.add(e['event_id'])
    if [e['timestamp_sec'] for e in req['events']]!=sorted(e['timestamp_sec'] for e in req['events']): raise ValueError('unordered events')
    if req['metrics']['window_seconds']!=w['end_sec']-w['start_sec']: raise ValueError('window metric mismatch')
def check_result(req, result):
    check_request(req)
    check_shape('AnalysisResult',result)
    for k in ['task_id','replay_id','run_id']:
        if req[k]!=result[k]: raise ValueError('result identity mismatch: '+k)
    ins=result['insight']
    if result['status']=='rejected':
        if ins is not None: raise ValueError('rejected result must not contain publishable insight')
        return
    if ins is None: raise ValueError('missing insight')
    for k in ['match_id','window','type','team_id','metrics']:
        if ins[k]!=req[k]: raise ValueError('source mismatch: '+k)
    valid={e['event_id'] for e in req['events']}
    if not set(ins['evidence_event_ids'])<=valid: raise ValueError('unknown evidence')
    for c in ins['claims']:
        if not set(c['evidence_event_ids'])<=set(ins['evidence_event_ids']): raise ValueError('claim evidence mismatch')
        if c['kind']=='metric':
            key=c['metric_key']
            if key is None or c['metric_value']!=req['metrics'][key]: raise ValueError('wrong metric claim')
        elif c['metric_key'] is not None or c['metric_value'] is not None: raise ValueError('interpretation must not supply numeric fact')
    if ins['verification']['status']!=result['status']: raise ValueError('verification mismatch')
    mode=ins['generation']['mode']
    if mode!='live_model' and result['status']!='fallback': raise ValueError('non-live generation cannot be passed')
    if mode=='live_model' and (not ins['generation']['model'] or ins['verification']['method']!='agent_and_code'): raise ValueError('missing live model evidence')
def can_publish(result, replay):
    return result['status'] in ('passed','fallback') and result['replay_id']==replay['replay_id'] and result['run_id']==replay['run_id'] and result['insight'] is not None and result['insight']['window']['end_sec']<=replay['clock_sec']
