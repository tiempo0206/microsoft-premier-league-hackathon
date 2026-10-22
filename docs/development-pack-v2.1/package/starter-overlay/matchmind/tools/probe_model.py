"""Default only checks config. --live explicitly sends one possibly billable model request."""
import argparse,json,os,time,urllib.request,urllib.error
def main():
    p=argparse.ArgumentParser(); p.add_argument('--live',action='store_true'); a=p.parse_args()
    provider=os.getenv('MATCHMIND_MODEL_PROVIDER','mock'); base=os.getenv('MATCHMIND_MODEL_BASE_URL','').rstrip('/'); model=os.getenv('MATCHMIND_MODEL_NAME',''); key=os.getenv('MATCHMIND_MODEL_API_KEY','')
    print(json.dumps({'provider':provider,'model':model,'base_url_configured':bool(base),'key_present':bool(key),'live_requested':a.live}))
    if not a.live: return
    if provider=='mock' or not(base.startswith('https://') and model and key) or 'REPLACE' in base: raise SystemExit('Configure a real HTTPS endpoint, model, and key locally. No request sent.')
    body={'model':model,'messages':[{'role':'system','content':'Return only json, exactly {"ok":true}. Do not include markdown.'},{'role':'user','content':'Return the json object now.'}],'response_format':{'type':'json_object'},'stream':False,'max_tokens':128}
    req=urllib.request.Request(base+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    t=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=20) as r: result=json.load(r)
        content=json.loads(result['choices'][0]['message']['content'])
        if content!={'ok':True}: raise ValueError('unexpected JSON result')
        print(json.dumps({'success':True,'served_model':result.get('model'),'elapsed_ms':round((time.monotonic()-t)*1000),'usage':result.get('usage')}))
    except urllib.error.HTTPError as e:
        print(json.dumps({'success':False,'http_status':e.code,'hint':'401 key/region; 403 permission; 404 model/base URL; 429 quota; 400 provider JSON parameters'})); raise SystemExit(1)
    except Exception as e:
        print(json.dumps({'success':False,'error_type':type(e).__name__})); raise SystemExit(1)
if __name__=='__main__': main()
