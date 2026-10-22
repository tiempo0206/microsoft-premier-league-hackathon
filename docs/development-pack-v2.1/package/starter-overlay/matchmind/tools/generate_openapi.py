import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'contracts/contract.schema.json').read_text(encoding='utf-8'))
schemas=json.loads(json.dumps(d['$defs']).replace('#/$defs/','#/components/schemas/'))
ref=lambda t:{'$ref':'#/components/schemas/'+t}
json_content=lambda s:{'application/json':{'schema':s}}
paths={}
def endpoint(path,method,result,request=None,status='200',array=False,query=()):
    result_schema={'type':'array','items':ref(result)} if array else ref(result)
    response={'description':'Success','content':json_content(result_schema)}
    if result=='STREAM': response={'description':'SSE stream; reconnect via snapshot','content':{'text/event-stream':{'schema':{'type':'string'}}}}
    op={'responses':{status:response,**{code:{'description':text,'content':json_content(ref('ErrorResponse'))} for code,text in [('400','Invalid request'),('404','Not found'),('409','State conflict'),('429','Capacity limit')]}}}
    pars=[]
    for part in path.split('/'):
        if part.startswith('{'): pars.append({'name':part[1:-1],'in':'path','required':True,'schema':{'type':'string'}})
    pars += [{'name':q,'in':'query','required':False,'schema':{'type':'integer','minimum':0}} for q in query]
    if result=='STREAM': pars.append({'name':'Last-Event-ID','in':'header','required':False,'schema':{'type':'string'}})
    if pars: op['parameters']=pars
    if request: op['requestBody']={'required':True,'content':json_content(ref(request))}
    paths.setdefault(path,{})[method]=op
endpoint('/api/v1/health','get','Health')
endpoint('/api/v1/matches','get','Match',array=True)
endpoint('/api/v1/matches/{match_id}','get','Match')
endpoint('/api/v1/matches/{match_id}/events','get','Event',array=True,query=('from_sec','to_sec'))
endpoint('/api/v1/matches/{match_id}/stats','get','MatchState',query=('at_sec',))
endpoint('/api/v1/replays','post','ReplaySnapshot','CreateReplay','201')
endpoint('/api/v1/replays/{replay_id}','get','ReplaySnapshot')
endpoint('/api/v1/replays/{replay_id}/control','post','ReplaySnapshot','ControlReplay')
endpoint('/api/v1/replays/{replay_id}/stream','get','STREAM')
endpoint('/api/v1/replays/{replay_id}/insights/{insight_id}','get','Insight')
out={'openapi':'3.1.0','info':{'title':'MatchMind API','version':'2.0.0'},'paths':paths,'components':{'schemas':schemas}}
(ROOT/'contracts/openapi.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Generated contracts/openapi.json')
