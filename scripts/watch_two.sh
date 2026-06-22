#!/usr/bin/env bash
sleep "${1:-2400}"
python3 -c "
import json, urllib.request
tok=open('/home/gradient/.kaggle/access_token').read().strip()
def api(s):
    req=urllib.request.Request('https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes',data=json.dumps({'submissionId':s}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+tok})
    return json.load(urllib.request.urlopen(req,timeout=30))
for name,S in [('v1 no-detect',53947755),('v2 +detect',$2)]:
    try:
        eps=api(S).get('episodes',[]); ms=[a for e in eps for a in e['agents'] if a.get('submissionId')==S]
        w=sum(1 for m in ms if m.get('reward')==1); l=sum(1 for m in ms if m.get('reward')==-1)
        elo=sorted(eps,key=lambda e:e.get('endTime',''))[-1]
        me=[a for a in elo['agents'] if a.get('submissionId')==S][0]
        print(f'{name}: Elo ~{me.get(\"updatedScore\") or 0:.0f}  {w}W-{l}L over {len(ms)} games')
    except Exception as ex: print(name,'err',ex)
"
