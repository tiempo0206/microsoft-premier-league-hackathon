"""Replacement boundary owned by Role C. This initial implementation is an honest offline stub."""
import copy, json
from pathlib import Path
from contracts.validation import check_request, check_result
ROOT=Path(__file__).resolve().parents[1]
async def analyze(request: dict) -> dict:
    check_request(request)
    # Stub is intentionally limited to the shipped fixture. Never invent generic statistics.
    example=json.loads((ROOT/'contracts/examples/analysis_request.json').read_text(encoding='utf-8'))
    if any(request[k]!=example[k] for k in ['match_id','window','type','team_id','events','metrics','language']):
        return {'task_id':request['task_id'],'replay_id':request['replay_id'],'run_id':request['run_id'],'status':'rejected','insight':None,'traces':[],'error':{'code':'MODEL_UNAVAILABLE','message':'Offline stub only supports the supplied example. Role C must implement general fallback.','retryable':False}}
    result=copy.deepcopy(json.loads((ROOT/'contracts/examples/analysis_result.json').read_text(encoding='utf-8')))
    for k in ['task_id','replay_id','run_id']: result[k]=request[k]
    result['insight']['insight_id']='INS-'+request['task_id']
    for trace in result['traces']: trace['task_id']=request['task_id']
    check_result(request,result)
    return result
