import json,threading,unittest,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
from tools.mock_api import Handler
from contracts.validation import check_shape
class MockAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close()
    def request(self,path,data=None):
        req=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=3) as r: return json.load(r)
    def create(self): return self.request('/api/v1/replays',{'match_id':'MM-DEMO-01','speed':5})
    def test_http_shapes(self):
        check_shape('Health',self.request('/api/v1/health'))
        check_shape('Match',self.request('/api/v1/matches')[0])
        snap=self.create(); check_shape('ReplaySnapshot',snap)
        self.assertEqual(snap['state']['passes'],{'HOME':0,'AWAY':0})
    def test_control_and_isolation(self):
        one,two=self.create(),self.create(); rid=one['replay']['replay_id']; rid2=two['replay']['replay_id']
        paused=self.request('/api/v1/replays/'+rid+'/control',{'action':'pause'})
        self.assertEqual(paused['replay']['status'],'paused')
        reset=self.request('/api/v1/replays/'+rid+'/control',{'action':'reset'})
        self.assertEqual(reset['replay']['run_id'],2)
        self.assertEqual(self.request('/api/v1/replays/'+rid2)['replay']['run_id'],1)
    def test_stream_starts_with_valid_snapshot(self):
        rid=self.create()['replay']['replay_id']
        with urllib.request.urlopen(self.base+'/api/v1/replays/'+rid+'/stream',timeout=3) as r:
            self.assertTrue(r.headers['Content-Type'].startswith('text/event-stream'))
            event=r.readline().decode().strip(); ident=r.readline().decode().strip(); data=r.readline().decode().strip()
        self.assertEqual(event,'event: snapshot'); self.assertTrue(ident.startswith('id: '+rid+':1:'))
        value=json.loads(data.removeprefix('data: ')); check_shape('StreamMessage',value)
    def test_unknown_match(self):
        with self.assertRaises(urllib.error.HTTPError) as cm: self.request('/api/v1/matches/NOPE')
        self.assertEqual(cm.exception.code,404)
if __name__=='__main__': unittest.main()
