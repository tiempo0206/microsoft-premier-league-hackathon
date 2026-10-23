"""Offline fixture oracle for tests and the mock only; no football ground-truth claim."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MATCH=json.loads((ROOT/'data/fixtures/demo.match.json').read_text(encoding='utf-8'))
EVENTS=[json.loads(s) for s in (ROOT/'data/fixtures/demo.events.jsonl').read_text(encoding='utf-8').splitlines() if s]
def state_at(at):
    at=max(MATCH['clip_start_sec'],min(at,MATCH['clip_end_sec']))
    seen=[e for e in EVENTS if e['timestamp_sec']<=at]
    state={'match_id':MATCH['match_id'],'at_sec':int(at),'score':{'HOME':0,'AWAY':0},'shots':{'HOME':0,'AWAY':0},'passes':{'HOME':0,'AWAY':0},'completed_passes':{'HOME':0,'AWAY':0},'possession_seconds':{'HOME':0,'AWAY':0},'last_event_id':seen[-1]['event_id'] if seen else None}
    initial_end=seen[0]['timestamp_sec'] if seen else at
    state['possession_seconds'][MATCH['initial_possession_team']]=max(0,int(initial_end-MATCH['clip_start_sec']))
    for i,e in enumerate(seen):
        team=e['team_id']; kind=e['type']
        if kind=='goal': state['score'][team]+=1
        if kind=='shot': state['shots'][team]+=1
        if kind=='pass':
            state['passes'][team]+=1
            if e['outcome']=='successful': state['completed_passes'][team]+=1
        end=seen[i+1]['timestamp_sec'] if i+1<len(seen) else at
        state['possession_seconds'][team]+=max(0,int(end-e['timestamp_sec']))
    return state
def window_metrics(start,end,team='HOME'):
    es=[e for e in EVENTS if start<=e['timestamp_sec']<=end]
    right=(MATCH['home_attack_direction']=='right')==(team=='HOME')
    high=[e for e in es if e['type']=='recovery' and e['team_id']==team and (e['position']['x'] if right else 100-e['position']['x'])>=66.67]
    linked=[r for r in high if any(e['type']=='shot' and e['team_id']==team and e['possession_id']==r['possession_id'] and 0<e['timestamp_sec']-r['timestamp_sec']<=15 for e in es)]
    s0,s1=state_at(start),state_at(end)
    return {'high_recoveries':len(high),'linked_shots':len(linked),'window_seconds':end-start,'home_possession_seconds':s1['possession_seconds']['HOME']-s0['possession_seconds']['HOME'],'away_possession_seconds':s1['possession_seconds']['AWAY']-s0['possession_seconds']['AWAY'],'home_shots':sum(e['type']=='shot' and e['team_id']=='HOME' for e in es),'away_shots':sum(e['type']=='shot' and e['team_id']=='AWAY' for e in es)}
