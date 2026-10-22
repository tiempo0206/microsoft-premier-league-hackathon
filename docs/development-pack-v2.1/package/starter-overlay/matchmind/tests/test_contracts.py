import asyncio,copy,json,unittest
from pathlib import Path
from contracts.validation import check_shape,check_request,check_result,can_publish
from tools.reference import EVENTS,MATCH,state_at,window_metrics
from ai.service import analyze
ROOT=Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT/'contracts/examples'/name).read_text(encoding='utf-8'))
class Contracts(unittest.TestCase):
    def setUp(self): self.req=load('analysis_request.json'); self.res=load('analysis_result.json')
    def test_all_shapes(self):
        for name,file in [('AnalysisRequest','analysis_request.json'),('AnalysisResult','analysis_result.json'),('ReplaySnapshot','replay_snapshot.json'),('StreamMessage','stream_message.json'),('CreateReplay','create_replay.json'),('ControlReplay','control_replay.json')]: check_shape(name,load(file))
        check_shape('Match',MATCH)
        for e in EVENTS: check_shape('Event',e)
    def test_valid_example(self): check_result(self.req,self.res)
    def test_unknown_id_rejected(self):
        self.res['insight']['evidence_event_ids'].append('invented')
        with self.assertRaises(ValueError): check_result(self.req,self.res)
    def test_bad_number_rejected(self):
        self.res['insight']['claims'][0]['metric_value']=9
        with self.assertRaises(ValueError): check_result(self.req,self.res)
    def test_wrong_match_rejected(self):
        self.req['events'][0]['match_id']='OTHER'
        with self.assertRaises(ValueError): check_request(self.req)
    def test_outside_window_rejected(self):
        self.req['events'][0]['timestamp_sec']=1400
        with self.assertRaises(ValueError): check_request(self.req)
    def test_fallback_cannot_be_live_passed(self):
        self.res['status']='passed'; self.res['insight']['verification']['status']='passed'
        with self.assertRaises(ValueError): check_result(self.req,self.res)
    def test_old_run_not_published(self):
        replay=load('replay_snapshot.json')['replay']; replay['run_id']=2
        self.assertFalse(can_publish(self.res,replay))
    def test_other_session_not_published(self):
        replay=load('replay_snapshot.json')['replay']; replay['replay_id']='OTHER'
        self.assertFalse(can_publish(self.res,replay))
    def test_future_not_published(self):
        replay=load('replay_snapshot.json')['replay']; replay['clock_sec']=1600
        self.assertFalse(can_publish(self.res,replay))
    def test_paused_current_result_allowed(self):
        self.assertTrue(can_publish(self.res,load('replay_snapshot.json')['replay']))
    def test_fixture_oracle(self):
        self.assertEqual(window_metrics(1500,1650),self.req['metrics'])
        self.assertEqual(state_at(1650),load('replay_snapshot.json')['state'])
        self.assertEqual(state_at(1800)['score'],{'HOME':1,'AWAY':0})
    def test_high_recovery_negative_window(self):
        self.assertLess(window_metrics(1500,1590)['high_recoveries'],3)
    def test_stub_with_identity(self):
        self.req.update(task_id='T2',replay_id='R2',run_id=9)
        res=asyncio.run(analyze(self.req)); check_result(self.req,res)
        self.assertEqual(res['status'],'fallback')
    def test_stub_does_not_fabricate_new_metrics(self):
        self.req['metrics']['high_recoveries']=8
        res=asyncio.run(analyze(self.req)); self.assertEqual(res['status'],'rejected'); check_result(self.req,res)
if __name__=='__main__': unittest.main()
