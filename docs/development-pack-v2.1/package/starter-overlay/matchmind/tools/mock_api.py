"""Local frontend contract mock. Not a production backend or real AI demonstration."""
import argparse, copy, json, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from tools.reference import MATCH, EVENTS, ROOT, state_at
from contracts.validation import check_shape
LOCK=threading.RLock(); SESSIONS={}
EXAMPLE=json.loads((ROOT/'contracts/examples/analysis_result.json').read_text(encoding='utf-8'))
def new_session(speed):
    rid='R-'+uuid.uuid4().hex
    return {'replay':{'replay_id':rid,'run_id':1,'match_id':MATCH['match_id'],'clock_sec':1500,'speed':speed,'status':'idle','last_seq':0},'insights':[],'traces':[],'updated':time.monotonic(),'clock_float':1500.0}
def advance(s):
    r=s['replay']; now=time.monotonic()
    if r['status']=='playing':
        s['clock_float']=min(1800,s['clock_float']+(now-s['updated'])*r['speed'])
        r['clock_sec']=int(s['clock_float'])
        if r['clock_sec']>=1800: r['status']='ended'
    s['updated']=now
    if r['clock_sec']>=1650 and not s['insights']:
        ins=copy.deepcopy(EXAMPLE['insight']); ins['insight_id']='INS-'+r['replay_id']+'-'+str(r['run_id'])
        s['insights']=[ins]; s['traces']=copy.deepcopy(EXAMPLE['traces'])
def snapshot(s):
    advance(s)
    return {'replay':copy.deepcopy(s['replay']),'state':state_at(s['replay']['clock_sec']),'insights':copy.deepcopy(s['insights']),'traces':copy.deepcopy(s['traces'])}
class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass
    def send_json(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def error(self,code='NOT_FOUND',status=404): self.send_json({'error':{'code':code,'message':code,'retryable':False}},status)
    def do_GET(self):
        u=urlparse(self.path); p=u.path.strip('/').split('/'); q=parse_qs(u.query)
        if u.path=='/api/v1/health': return self.send_json({'status':'ok','contract_version':'2.0.0','mode':'mock','model_ready':False})
        if u.path=='/api/v1/matches': return self.send_json([MATCH])
        if len(p)>=4 and p[:3]==['api','v1','matches']:
            if p[3]!=MATCH['match_id']: return self.error()
            if len(p)==4: return self.send_json(MATCH)
            if p[4]=='events':
                try: start=int(q.get('from_sec',['1500'])[0]); end=int(q.get('to_sec',['1800'])[0])
                except ValueError: return self.error('INVALID_REQUEST',400)
                return self.send_json([e for e in EVENTS if start<=e['timestamp_sec']<=end])
            if p[4]=='stats':
                try: at=int(q.get('at_sec',['1500'])[0])
                except ValueError: return self.error('INVALID_REQUEST',400)
                return self.send_json(state_at(at))
        if len(p)>=4 and p[:3]==['api','v1','replays']:
            with LOCK:
                s=SESSIONS.get(p[3])
                if not s: return self.error()
                if len(p)==4: return self.send_json(snapshot(s))
                if p[4]=='insights' and len(p)==6:
                    advance(s); ins=next((x for x in s['insights'] if x['insight_id']==p[5]),None)
                    return self.send_json(ins) if ins else self.error()
            if p[4]=='stream': return self.stream(s)
        return self.error()
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>10000: return self.error('INVALID_REQUEST',400)
            body=json.loads(self.rfile.read(length))
        except (ValueError,json.JSONDecodeError): return self.error('INVALID_REQUEST',400)
        p=urlparse(self.path).path.strip('/').split('/')
        with LOCK:
            if p==['api','v1','replays']:
                try: check_shape('CreateReplay',body)
                except Exception: return self.error('INVALID_REQUEST',400)
                if body.get('match_id')!=MATCH['match_id'] or body.get('speed') not in [1,2,5,10]: return self.error('INVALID_REQUEST',400)
                s=new_session(body['speed']); SESSIONS[s['replay']['replay_id']]=s
                return self.send_json(snapshot(s),201)
            if len(p)==5 and p[:3]==['api','v1','replays'] and p[4]=='control':
                try: check_shape('ControlReplay',body)
                except Exception: return self.error('INVALID_REQUEST',400)
                s=SESSIONS.get(p[3])
                if not s: return self.error()
                advance(s); r=s['replay']; action=body.get('action')
                if action=='reset':
                    r.update(run_id=r['run_id']+1,clock_sec=1500,status='idle'); s.update(insights=[],traces=[],clock_float=1500.0)
                elif action=='play':
                    if r['status']=='ended': return self.error('STATE_CONFLICT',409)
                    r['status']='playing'
                elif action=='pause':
                    if r['status']!='ended': r['status']='paused'
                elif action=='set_speed' and body.get('speed') in [1,2,5,10]: r['speed']=body['speed']
                else: return self.error('INVALID_REQUEST',400)
                s['updated']=time.monotonic()
                return self.send_json(snapshot(s))
        return self.error()
    def stream(self,s):
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Cache-Control','no-cache'); self.send_header('Connection','keep-alive'); self.end_headers()
        # Mock sends complete snapshots so frontend can be developed without production fan-out.
        # Actual backend must also implement the other frozen stream kinds and bounded subscribers.
        try:
            while True:
                with LOCK:
                    snap=snapshot(s); s['replay']['last_seq']+=1; snap['replay']['last_seq']=s['replay']['last_seq']
                    r=snap['replay']; msg={'replay_id':r['replay_id'],'run_id':r['run_id'],'seq':r['last_seq'],'kind':'snapshot','payload':snap}
                data='event: snapshot\nid: '+r['replay_id']+':'+str(r['run_id'])+':'+str(r['last_seq'])+'\ndata: '+json.dumps(msg,ensure_ascii=False)+'\n\n'
                self.wfile.write(data.encode()); self.wfile.flush(); time.sleep(0.25)
        except OSError: return
        finally: self.close_connection=True
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=8765); args=ap.parse_args()
    print(f'LOCAL MOCK ONLY http://127.0.0.1:{args.port}; no model calls',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
