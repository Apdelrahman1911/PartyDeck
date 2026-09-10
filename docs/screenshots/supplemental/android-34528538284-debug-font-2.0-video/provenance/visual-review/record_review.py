import pathlib, json, datetime
ROOT=pathlib.Path('/tmp/partydeck-video-review-34528538284-design-v1')
def record(clip_name, batches):
    plan=json.loads((ROOT/'review-plan.json').read_text())
    clip=next(c for c in plan['clips'] if c['name']==clip_name)
    frames={f['frameNumber']:f for f in clip['directViewPlan']}
    log=ROOT/'direct-observations.jsonl'
    old=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    seen={(v['clip'],v['frameNumber']) for v in old}
    new=[]
    for batch in batches:
        for number in batch['frames']:
            assert (clip_name,number) not in seen
            frame=frames[number]
            new.append({'clip':clip_name,'frameNumber':number,'frameIndex':number-1,'originalPath':clip['original']['originalPath'],'originalSha256':clip['original']['sha256'],'derivativePath':frame['path'],'derivativeSha256':frame['sha256'],'mediaPts':frame['bestEffortTimestamp'],'mediaPtsSeconds':frame['bestEffortTimestampSeconds'],'mediaTimeBase':'1/90000','displayedDimensions':[1600,720],'method':'direct_full_frame_original_size_view_image','recordedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'noteTimestampScope':'Observation receipt written after the pixel view; not a capture timestamp.','state':batch['state'],'observations':batch['observations'],'privateCardFacesVisible':batch['privateCardFacesVisible'],'byteIdenticalFrameNumbers':[i+1 for i in frame['groupIndices']]})
            seen.add((clip_name,number))
    with log.open('a') as f:
        for row in new: f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({'clip':clip_name,'newDirectObservations':len(new),'allDirectObservations':len(old)+len(new)}))
