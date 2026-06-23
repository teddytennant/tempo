#!/usr/bin/env bash
sleep "${1:-2700}"
python3 -c "
import json, urllib.request
tok=open('/home/gradient/.kaggle/access_token').read().strip()
def api(s):
    req=urllib.request.Request('https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes',data=json.dumps({'submissionId':s}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+tok})
    return json.load(urllib.request.urlopen(req,timeout=30))
for name,S in [('Iono ',53960659),('Crustle',53960682)]:
    try:
        eps=sorted(api(S).get('episodes',[]),key=lambda e:e.get('endTime',''))
        ms=[a for e in eps for a in e['agents'] if a.get('submissionId')==S]
        w=sum(1 for m in ms if m.get('reward')==1); l=sum(1 for m in ms if m.get('reward')==-1)
        elo=ms[-1].get('updatedScore') if ms else 0
        print(f'{name}: Elo ~{(elo or 0):.0f}  {w}W-{l}L / {len(ms)} games')
    except Exception as ex: print(name,'pending/err',str(ex)[:60])
"
