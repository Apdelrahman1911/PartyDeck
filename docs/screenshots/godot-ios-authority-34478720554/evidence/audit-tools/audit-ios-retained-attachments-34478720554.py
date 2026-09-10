"""Verify original XCResult attachments and bounded retained observations, without native execution."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import sys
BASE = Path('/tmp/partydeck-engine-ci/34478720554')
HEAD = 'c6ea1dd9f7966517fbee87a06b633d01c432c24d'
HOST = BASE / 'godot-ios-retained-host-test-attempt-1/retained-host-test'
ARTIFACTS = HOST / 'artifacts'
ATTACHMENTS = ARTIFACTS / 'attachments'
BUNDLE = ARTIFACTS / 'RetainedHost.xcresult'
DECODED = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34478720554-retained-xcresult-decoded')
SOURCE = BASE / 'source-c6ea1dd'
sys.path.insert(0, str(SOURCE / 'godot/android-checks'))
from evidence import read_png

def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def record(path): return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)}
def write_new(path,value):
    with path.open('x') as f: json.dump(value,f,indent=2);f.write('\n')
checks=[]
def check(label, condition):
    checks.append({'check':label,'passed':bool(condition)})
    assert condition,label

def native(m):return m['native']
def renderer(m):return native(m)['rendererDiagnostics']
def stable(m):return {k:native(m)[k] for k in ['engineIdentity','viewIdentity','controllerIdentity','layerIdentity','processIdentifier']}
def concealed(m):
    d=renderer(m)
    return d.get('handConcealed') is True and all(d.get(k)==0 for k in ['selectedCount','privateFaceCount','privateLabelCount'])
def count(m,k):return int(m[k])
def no_work(before,after,label):
    a,b=native(before),native(after)
    names=['iterations','drawCalls','nativePresentedFrames','nativeFailedPresentations','readyEvents','intentEvents','exitEvents','engineFramesDrawn','treeIdentity']
    check(label+' stopped native work counters and tree',all(a[k]==b[k] for k in names))
    check(label+' stopped audio counters',all(a['audio'][k]==b['audio'][k] for k in ['callbackEntries','startAttempts','stopAttempts']))
    check(label+' stable retained identity',stable(before)==stable(after))

def dormant(m,label):
    n=native(m);a=n['audio'];ret=n['audioRetirement']
    check(label+' dormant native owner and authority release',m['state']=='dormant' and n['state']=='dormant' and n['dormant'] and m['authorityReleased'] and n['retainedEnginePolicy'])
    check(label+' retained engine and empty replacement tree',n['bootstrapCount']==1 and n['cleanupCount']==0 and n['osSingletonPresent'] and n['bridgeRegistered'] and n['emptyTree'] and n['emptyTreeNodeCount']==1 and n['oldSceneObjectsAbsent'] and n['retiredNodeCount']>1 and n['bridgeConnections']==0)
    check(label+' surface detached and native input disabled',n['neutralFramePresented'] and not n['surfaceAttached'] and not n['renderLoopActive'] and n['inputViewEnabled'] is False and n['surfaceAccessibilityHidden'] and not n['eventHandlerPresent'] and not n['sdlEnabled'] and not n['quarantined'])
    check(label+' idle timer restored',n['idleTimerPolicyRestored'] and n['idleTimerDisabled']==n['previousIdleTimerDisabled'])
    check(label+' queues and retirement depths empty',all(n[k]==0 for k in ['queuedCommands','queuedEvents','queuedBytes','queuedPrivateDocuments','cancelledDeliveryCallbacks','drawDepth','retirementDepth']) and n['rendererDiagnostics']=={} and m['modelQueuedDocuments']==0 and not m['modelDeliveryPending'] and m['retiredCallbacksAfterClose']==0)
    check(label+' actual CoreAudio stop and quiescence',a['driver']=='CoreAudio' and a['observed'] and a['outputUnitPresent'] and not a['inputUnitPresent'] and not a['active'] and a['callbacksInFlight']==0 and a['lastStopStatus']==0 and a['stopAttempts']>0 and a['stoppedStartAttempt']==a['startAttempts'] and n['audioQuiescenceObserved'])
    check(label+' audio residuals retired',ret['error']==0 and all(ret[k] for k in ['preflightPassed','playbackCleanupSucceeded','callbackCleanupSucceeded','busDetailsCleanupSucceeded','oldBusDetailsCleanupSucceeded','residualsObserved','serverBuffersNeutral','driverBufferNeutral','driverQuiescent']) and all(ret[k]==0 for k in ['playbacksRemaining','callbacksRemaining','busDetailsRemaining','samplePlaybacksRemaining']))
    check(label+' simulator motion observed unavailable and inactive',n['motion']['available'] is False and n['motion']['active'] is False)

def closure(c,label):
    check(label+' completion follows request and early return',c['completionObserved'] and c['dormant'] and c['returnedBeforeCompletion'] and c['completedAtUptime']-c['requestedAtUptime']>=c['completionNative']['audioObservationMinimumSeconds'])
    check(label+' new handle refused during close',c['openWhileClosingRefused'] and bool(c['openWhileClosingError']))
    check(label+' authority and handle ownership released',all(c[k] for k in ['authorityReleased','authorityLaunchCleared','handleViewControllerReleased','handleCallbacksCleared']) and c['authorityStatus']['lifecycle']=='CLOSED' and c['callbacksAfterClose']==0)
    r,n=c['returnedNative'],c['completionNative']
    check(label+' early cover and event queue suppression',r['privacyCoverVisible'] and not any(r[k] for k in ['presentationActive','renderLoopActive','eventHandlerPresent']) and r['queuedPrivateDocuments']==0)
    check(label+' completion reports actual dormancy',n['state']=='dormant' and n['retirementDepth']==0)

con=sqlite3.connect('file:'+str(BUNDLE/'database.sqlite3')+'?mode=ro',uri=True)
con.row_factory=sqlite3.Row
tests=[dict(row) for row in con.execute('SELECT c.name,c.identifier,r.rowid AS runRow,r.result,r.duration FROM TestCaseRuns r JOIN TestCases c ON r.testCase_fk=c.rowid ORDER BY c.rowid')]
issues=[dict(row) for row in con.execute('SELECT testCaseRun_fk,compactDescription,detailedDescription,issueType FROM TestIssues')]
expected_names={'testActiveAndDormantBackgroundTransitionsStayConcealed()','testRepeated2DAnd3DKeepOneDormantEngine()','testStaleFirstReadyAndCloseCompletionReentry()'}
expected={t['name']:t['result'] for t in tests}
check('exact three source-declared cases in original XCResult',len(tests)==3 and set(expected)==expected_names)
check('original cases report success or failure',all(status in {'Success','Failure'} for status in expected.values()))
check('no skipped retained cases',con.execute('SELECT count(*) FROM SkipNotices').fetchone()[0]==0)
result=read(HOST/'evidence/result.json')
check('three started and completed cases match recorded runner result',set(result['native_tests_started'])=={name[:-2] for name in expected} and {t['case']:t['status'] for t in result['native_tests']}=={name[:-2]:('passed' if status=='Success' else 'failed') for name,status in expected.items()})
qualified=all(status=='Success' for status in expected.values()) and result['command_exit_code']==0 and not result['problems']
check('suite qualification matches complete original results',result['retained_engine_lifecycle_qualified']==result['same_process_reentry_qualified']==qualified)
rows={row['uuid']:dict(row) for row in con.execute('SELECT rowid,uuid,name,filenameOverride,xcResultKitPayloadRefId FROM Attachments')}
objects={Path(r['source']).name.removeprefix('data.'):r for r in read(DECODED/'decoded-object-index.json')['dataObjects']}
manifest=read(ATTACHMENTS/'manifest.json')
records=[];per_test=[]
for tm in manifest:
    identifier=tm['testIdentifier'];case=next(t for t in tests if t['identifier']==identifier)
    measurements=[];targets=[];intervals=[];homes=[];rejected=[];case_records=[]
    for item in sorted(tm['attachments'],key=lambda x:x['timestamp']):
        p=ATTACHMENTS/item['exportedFileName'];row=rows[p.stem];obj=objects[row['xcResultKitPayloadRefId']]
        check(identifier+' original attachment '+p.name,digest(p)==obj['decodedSha256'] and p.stat().st_size==obj['decodedBytes'])
        rec={**record(p),'name':item['suggestedHumanReadableName'],'timestamp':item['timestamp'],'testIdentifier':identifier,'attachmentUuid':row['uuid'],'xcresultPayloadRef':row['xcResultKitPayloadRefId'],'xcresultOriginalObject':obj['source'],'xcresultOriginalObjectSha256':obj['sourceSha256'],'xcresultPayloadSha256':obj['decodedSha256'],'matchesOriginalXcresultPayload':True}
        if p.suffix=='.png':
            picture=read_png(p.read_bytes());rec.update(width=picture.width,height=picture.height,pngVerifiedAndDecoded=True)
        if p.suffix=='.json':
            v=read(p);entry={'name':rec['name'],'file':str(p),'timestamp':rec['timestamp'],'value':v}
            if 'native' in v:measurements.append(entry);rec['jsonKind']='measurement'
            elif {'action','control','metrics'}<=set(v):
                c=v['control'];m=v['metrics'];r=c['rect'];clip=c['clipRect'];vp=renderer(m)['viewport']
                check(identifier+' touch candidate clip '+p.name,c['enabled'] and clip[0]>=-0.5 and clip[1]>=-0.5 and clip[0]+clip[2]<=vp['width']+0.5 and clip[1]+clip[3]<=vp['height']+0.5)
                eligible=c['visible'] and r[0]>=clip[0]-0.5 and r[1]>=clip[1]-0.5 and r[0]+r[2]<=clip[0]+clip[2]+0.5 and r[1]+r[3]<=clip[1]+clip[3]+0.5
                if eligible:check(identifier+' eligible touch target minimum size '+p.name,r[2]>=44 and r[3]>=44)
                entry['eligibleVisibleTarget']=bool(eligible);targets.append(entry);rec['jsonKind']='measured_touch_candidate'
            elif {'before','after','samples'}<=set(v):intervals.append(entry);rec['jsonKind']='dormant_interval'
            elif {'timeoutSeconds','elapsedSeconds','measurements'}<=set(v):rejected.append(entry);rec['jsonKind']='last_rejected_wait_observation'
            elif {'applicationState','springboardState','dockIcons'}<=set(v):homes.append(entry);rec['jsonKind']='observed_home_state'
            else:rec['jsonKind']='other'
        records.append(rec);case_records.append(rec)
    run_ids={m['value']['runID'] for m in measurements if 'runID' in m['value']}
    run_ids.update(m['value']['measurements']['runID'] for m in rejected if 'runID' in m['value']['measurements'])
    check(identifier+' at most one observed application run ID',len(run_ids)<=1)
    if case['result']=='Success': check(identifier+' passing case supplies application run identity',len(run_ids)==1)
    run_id=next(iter(run_ids),None)
    journal_path=HOST/'evidence/application-observations'/('retained-runtime-'+run_id+'.json') if run_id else None
    journal=read(journal_path) if journal_path and journal_path.is_file() else {'journal':[],'arguments':[]}
    if journal_path and journal_path.is_file():
        check(identifier+' journal matches attachment run identity',journal['runID']==run_id and all(x['measurements']['runID']==run_id for x in journal['journal']))
    validated=[]
    for index,item in enumerate(intervals,1):
        v=item['value'];a,b=v['before'],v['after'];label=identifier+' dormant interval '+str(index)
        dormant(a,label+' before');dormant(b,label+' after');no_work(a,b,label)
        check(label+' responsive shell and measured duration',b['hostCounter']==a['hostCounter']+1 and b['pollCount']>a['pollCount'] and v['samples']>=2 and b['observedUptime']-a['observedUptime']>=max(0.8,native(a)['audioObservationMinimumSeconds']))
        item['verifiedDurationSeconds']=b['observedUptime']-a['observedUptime']
    accepted_dormant=[m for m in measurements if m['name'].startswith(('Dormant Home/activate accepted native observation','Dormant Homeactivate accepted native observation'))]
    check(identifier+' at most one accepted dormant Home/activate payload',len(accepted_dormant)<=1)
    if accepted_dormant:
        check(identifier+' accepted dormant payload belongs to background case',case['name']=='testActiveAndDormantBackgroundTransitionsStayConcealed()')
        accepted=accepted_dormant[0]['value']
        dormant(accepted,identifier+' exact accepted dormant Home/activate')
        check(identifier+' exact accepted observation is active and not backgrounded',native(accepted)['applicationActive'] is True and native(accepted)['applicationBackgrounded'] is False)
        check(identifier+' pre-Home interval is preserved',len(intervals)>=1)
        before_home=intervals[0]['value']['after']
        check(identifier+' exact accepted observation includes a new background callback',accepted['applicationBackgroundCount']>before_home['applicationBackgroundCount'])
        no_work(before_home,accepted,identifier+' exact accepted dormant Home/activate')
        if len(intervals)>=2:
            check(identifier+' accepted dictionary exactly matches the next dormant interval baseline',accepted==intervals[1]['value']['before'])
    if case['result']=='Success' and case['name']=='testRepeated2DAnd3DKeepOneDormantEngine()':
        entries=[m for m in measurements if m['name'].startswith('Entry ')]
        plays=[m for m in measurements if m['name'].startswith('Real play accepted')]
        closes=[m for m in measurements if m['name'].startswith('Whole recipient scene retired')]
        check(identifier+' four entries, plays, exits and dormant intervals',len(entries)==len(plays)==len(closes)==len(intervals)==4)
        check(identifier+' expected real presentation sequence',[m['value']['mode'] for m in entries]==['2d','3d','2d','3d'])
        identity=stable(entries[0]['value'])
        check(identifier+' retained engine, view, controller, layer and process',identity['processIdentifier']>0 and all(stable(m['value'])==identity for m in entries+plays+closes))
        check(identifier+' fresh presentation, scene and tree identities',all(len({m['value']['presentationID'] if k=='presentationID' else native(m['value'])[k] for m in entries})==4 for k in ['presentationID','sceneIdentity','treeIdentity']))
        for index,(entry,played,closed) in enumerate(zip(entries,plays,closes),1):
            e,p,c=entry['value'],played['value'],closed['value'];n=native(e);label=identifier+' entry '+str(index)
            check(label+' fresh authority concealed at revision one',e['entryCount']==index and e['state']=='running' and e['lifecycle']=='READY' and e['revision']=='1' and e['readyConfirmed'] and not e['authorityReleased'] and e['acceptedViewerPlays']==0 and concealed(e) and renderer(e)['presentationId']==e['presentationID'] and renderer(e)['revision']==e['revision'])
            check(label+' retained native engine draw identity',n['presentationCount']==index and n['bootstrapCount']==1 and n['cleanupCount']==0 and n['readyEvents']==1 and n['nativePresentedFrames']>0 and n['nativeFailedPresentations']==0 and n['renderingLayerClass']=='GDTOpenGLLayer' and n['authorityReadyConfirmed'] and not e['entryPreparedNative']['authorityReadyConfirmed'])
            check(label+' actual play and subsequent concealment',p['acceptedViewerPlays']==1 and p['entryCount']==index and concealed(p) and int(native(p)['audio']['callbackEntries'])>0 and native(p)['intentEvents']>0)
            dormant(c,label+' close');closure(c['lastClosure'],label+' closure')
            check(label+' real scene exit and replacement tree',c['lastClosure']['reason']=='EXIT_REQUESTED' and native(c)['previousSceneIdentity']==n['sceneIdentity'] and native(c)['previousTreeIdentity']==n['treeIdentity'] and native(c)['treeIdentity']!=n['treeIdentity'])
            if index>1:
                previous=intervals[index-2]['value']['after']
                check(label+' next entry adopts previous empty tree after warmup',n['treeIdentity']==native(previous)['treeIdentity'] and n['warmupFrames']>native(previous)['warmupFrames'] and int(n['presentationGeneration'])>int(native(entries[index-2]['value'])['presentationGeneration']))
        check(identifier+' original idle timer off preserved','--host-idle-timer=off' in journal['arguments'] and all(native(c['value'])['previousIdleTimerDisabled'] is False for c in closes))
        check(identifier+' four ordered journal close pairs',[x['event'] for x in journal['journal']]==['close-requested','close-completed']*4)
        validated=['four real 2D/3D entries with fresh presentation/scene/tree identities','same retained engine/view/controller/layer and process','one actual accepted viewer play per entry','native scene retirement and ownership release before completion','four responsive dormant shell intervals with stopped draw/audio counters','idle timer initially off restored']
    elif case['result']=='Success' and case['name']=='testActiveAndDormantBackgroundTransitionsStayConcealed()':
        selected=[m['value'] for m in measurements if m['name'].startswith('Real reveal and card selection')]
        cycled=next(m['value'] for m in measurements if m['name'].startswith('Coalesced native foreground'))
        returned=next(m['value'] for m in measurements if m['name'].startswith('Real background and resume'))
        closes=[m['value'] for m in measurements if m['name'].startswith('Whole recipient scene retired')]
        check(identifier+' observed selected private presentation before transitions',len(selected)==3 and all(renderer(m)['selectedCount']==1 and renderer(m)['privateFaceCount']>0 and renderer(m)['privateLabelCount']>0 for m in selected))
        check(identifier+' coalesced focus cycle returns concealed',cycled['focusCycleCount']==selected[0]['focusCycleCount']+1 and int(native(cycled)['lifecycleGeneration'])>int(native(selected[0])['lifecycleGeneration']) and concealed(cycled) and not native(cycled)['privacyCoverVisible'])
        action_keys=['acceptedOpponentActions','acceptedViewerPlays','acceptedViewerChallenges','roundsAdvanced']
        check(identifier+' transitions preserve authority action counts',all(all(m[k]==selected[0][k] for k in action_keys) for m in selected+[cycled,returned]))
        check(identifier+' Home return same retained authority and concealed projection',returned['presentationID']==selected[-1]['presentationID'] and stable(returned)==stable(selected[-1]) and concealed(returned) and returned['applicationBackgroundCount']>selected[-1]['applicationBackgroundCount'] and int(native(returned)['lifecycleGeneration'])>int(native(selected[-1])['lifecycleGeneration']))
        check(identifier+' two actual Home dock observations',len(homes)==2 and all(h['value']['springboardState']==4 and h['value']['applicationState']!=1 and len(h['value']['dockIcons'])==2 and {i['identifier'] for i in h['value']['dockIcons']}=={'Safari','Messages'} and all(len(i['frame'])==4 and i['frame'][2]>0 and i['frame'][3]>0 for i in h['value']['dockIcons']) for h in homes))
        check(identifier+' two dormant intervals and two scene exits',len(intervals)==len(closes)==2)
        check(identifier+' passing background case preserves exact accepted dormant observation',len(accepted_dormant)==1)
        no_work(intervals[0]['value']['after'],intervals[1]['value']['before'],identifier+' dormant Home/activate')
        check(identifier+' dormant Home reached application callbacks',intervals[1]['value']['before']['applicationBackgroundCount']>intervals[0]['value']['after']['applicationBackgroundCount'] and native(intervals[1]['value']['before'])['applicationActive'] and not native(intervals[1]['value']['before'])['applicationBackgrounded'])
        for index,c in enumerate(closes,1):dormant(c,identifier+' close '+str(index));closure(c['lastClosure'],identifier+' closure '+str(index))
        check(identifier+' next 3D presentation retains engine and has fresh scene',[m['mode'] for m in closes]==['2d','3d'] and closes[0]['presentationID']!=closes[1]['presentationID'] and stable(closes[0])==stable(closes[1]) and native(closes[0])['sceneIdentity']!=native(closes[1])['sceneIdentity'])
        check(identifier+' original idle timer on restored','--host-idle-timer=on' in journal['arguments'] and all(native(c)['previousIdleTimerDisabled'] is True for c in closes))
        validated=['coalesced native focus cycle returns concealed without authority gameplay action','actual Home dock and native background callback evidence','same active authority retained and concealed after Home/activate','dormant Home/activate preserves stopped native/audio counters','fresh 3D entry in same retained engine','idle timer initially on restored']
    elif case['result']=='Success':
        probe_records=[m['value'] for m in measurements if m['name'].startswith('Old native handle refused')]
        plays=[m['value'] for m in measurements if m['name'].startswith('Real play accepted')]
        closes=[m['value'] for m in measurements if m['name'].startswith('Whole recipient scene retired')]
        check(identifier+' stale-handle checkpoint, play, close and dormant interval present',len(probe_records)==len(plays)==len(closes)==len(intervals)==1)
        probed,played,closed=probe_records[0],plays[0],closes[0]
        check(identifier+' both replacement close pairs recorded',[entry['event'] for entry in journal['journal']]==['close-requested','close-completed']*2)
        first=journal['journal'][0]['measurements'];probe=first['firstReadyProbe'];stale=probed['staleProbe']
        check(identifier+' initial stale Ready rejected',probe['attempted'] and probe['completed'] and not probe['accepted'] and not probe['nativeReadyConfirmedAtRejection'] and int(probe['currentGeneration'])>int(probe['capturedGeneration']) and probe['reportedGenerationBeforeCompletion']==probe['currentGeneration'])
        check(identifier+' same retained identity and fresh second 3D presentation',probed['entryCount']==2 and probed['mode']=='3d' and probed['presentationID']!=first['presentationID'] and stable(probed)==stable(first)==stable(played)==stable(closed) and concealed(probed))
        closure(probed['lastClosure'],identifier+' switch closure')
        check(identifier+' switch originated from close completion',probed['lastClosure']['reason']=='SWITCH_FROM_CLOSE_COMPLETION')
        check(identifier+' old handle refused all captured mutations and rebinding',all(stale[k] for k in ['deliveryCompleted','closeCompleted','callbackRebindingRefused','oldCloseDormant']) and not any(stale[k] for k in ['sendAccepted','deliveryAccepted','readyConfirmationAccepted','diagnosticsAccepted']) and probed['retiredCallbacksAfterClose']==0)
        check(identifier+' one real play accepted on new presentation',probed['acceptedViewerPlays']==0 and played['acceptedViewerPlays']==1 and played['presentationID']==probed['presentationID'] and concealed(played))
        dormant(closed,identifier+' final dormancy');closure(closed['lastClosure'],identifier+' final closure')
        check(identifier+' final real exit reason',closed['lastClosure']['reason']=='EXIT_REQUESTED')
        validated=['initial stale Ready rejection observed','new 3D presentation in the same retained engine process','old-handle mutation, grant, callback rebinding and repeated-close rejection observed','one real accepted viewer play followed by real exit','responsive dormant shell interval with stopped draw/audio counters']
    else:
        completed=[entry['measurements'] for entry in journal['journal'] if entry['event']=='close-completed']
        for index,completed_value in enumerate(completed,1):
            closure(completed_value['lastClosure'],identifier+' recorded completed close '+str(index))
        validated=['original failed case, issue records and all captured observations preserved','no full-case behavior or missing checkpoint inferred from partial evidence']
        if completed: validated.append(str(len(completed))+' completed closure observations independently checked')
        if rejected: validated.append(str(len(rejected))+' original last-rejected wait observations preserved separately from later capture')
    per_test.append({**case,'issues':[i for i in issues if i['testCaseRun_fk']==case['runRow']],'attachmentCount':len(case_records),'byExtension':dict(Counter(Path(r['path']).suffix for r in case_records)),'runID':run_id,'applicationJournal':record(journal_path) if journal_path and journal_path.is_file() else None,'journalArguments':journal['arguments'],'measurements':measurements,'touchCandidates':targets,'touchCandidatesByAction':dict(Counter(t['value']['action'] for t in targets)),'eligibleVisibleTargetCount':sum(t['eligibleVisibleTarget'] for t in targets),'dormantIntervals':intervals,'homeObservations':homes,'lastRejectedWaitObservations':rejected,'independentlyVerifiedScope':validated})
    per_test[-1]['acceptedDormantHomeObservations']=accepted_dormant
    print(json.dumps({'test':identifier,'result':case['result'],'attachments':len(case_records),'measurements':len(measurements),'touchCandidates':len(targets),'dormantIntervals':len(intervals),'acceptedDormantHomeObservations':len(accepted_dormant)}),flush=True)
check('exact manifest case inventory',{t['identifier'] for t in tests}=={m['testIdentifier'] for m in manifest})
check('all exported original attachment payloads verified',len(records)==sum(len(item['attachments']) for item in manifest) and len({item['path'] for item in records})==len(records) and bool(records))
summary={'runId':34478720554,'headSha':HEAD,'attempt':1,'scope':'Original attachment identity and independently verified bounded Simulator observations. Actual outcomes are read from XCResult without an expected pass/fail assumption. Touch-candidate attachments precede the last input eligibility check and are not counted as actual taps. Home evidence preserves raw applicationState even when it reports foreground alongside observed SpringBoard dock icons.','manifest':record(ATTACHMENTS/'manifest.json'),'sqlite':record(BUNDLE/'database.sqlite3'),'decodedObjectIndex':record(DECODED/'decoded-object-index.json'),'originalResult':record(HOST/'evidence/result.json'),'inputAudit':record(BASE/'retained-input-evidence-summary.json'),'packageAudit':record(BASE/'retained-package-evidence-summary.json'),'attachmentCount':len(records),'xcresultHashMatchedAttachments':len(records),'pngCount':sum(Path(r['path']).suffix=='.png' for r in records),'measurementCount':sum(len(t['measurements']) for t in per_test),'touchCandidateCount':sum(len(t['touchCandidates']) for t in per_test),'dormantIntervalCount':sum(len(t['dormantIntervals']) for t in per_test),'lastRejectedWaitObservationCount':sum(len(t['lastRejectedWaitObservations']) for t in per_test),'testResults':dict(Counter(t['result'] for t in tests)),'tests':per_test,'attachments':records,'checks':checks,'retainedEngineLifecycleQualified':qualified,'sameProcessReentryQualified':qualified,'physicalSensorsQualified':False,'deviceMetalQualified':False,'actualAudioInterruptionQualified':False,'limitations':['Intermediate dormant samples are represented by the recorded sample count and endpoint measurements; all original XCResult and journals remain available.','Passing XCTest pause assertions are not independently reconstructed from AX logs in this attachment audit.','A failed case is not promoted by selected successful observed substeps.','Pixel/interaction review and source failure diagnosis are separate owner supplements.']}
output=BASE/'retained-attachment-evidence-summary.json';write_new(output,summary)
print(json.dumps({'receipt':record(output),'checksPassed':len(checks),'attachments':len(records),'pngs':summary['pngCount'],'dormantIntervals':summary['dormantIntervalCount']}),flush=True)
