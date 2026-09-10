"""Freeze the completed collection and independent audits without rewriting original evidence."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
BASE=Path('/tmp/partydeck-engine-ci/34464316979')
HEAD='ea84bf49e799675c181545cc3511460b11e0e23d'
def read(path):return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def record(path):return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)}
def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
run=read(BASE/'last-run-status.json');jobs=read(BASE/'last-jobs-status.json')['jobs'];contract=read(BASE/'collection-contract.json');complete=read(BASE/'collection-complete.json')
assert run['id']==34464316979 and run['head_sha']==HEAD and run['run_attempt']==1 and run['path']=='.github/workflows/godot-ios-authority-host.yml' and run['event']=='workflow_dispatch' and run['status']=='completed' and run['conclusion']=='failure'
assert complete['headSha']==HEAD and complete['attempt']==1 and complete['missingExpectedArtifacts']==[] and complete['collectionErrors']=={} and set(complete['downloadedArtifacts'])==set(contract['expectedArtifacts'])
api_artifacts={a['id']:a for a in read(BASE/'artifacts.json')['artifacts']}
artifacts=[]
for name in contract['expectedArtifacts']:
    integrity_path=BASE/(name+'.integrity.json');i=read(integrity_path);a=api_artifacts[i['artifactId']]
    archive=Path(i['archivePath']);r=record(archive)
    assert i['runId']==34464316979 and i['headSha']==HEAD and i['name']==a['name']==name and i['zipDigestMatchesApi'] and i['zipSizeMatchesApi']
    assert 'sha256:'+r['sha256']==i['archiveDigest']==i['apiDigest']==a['digest'] and r['bytes']==i['archiveBytes']==i['apiBytes']==a['size_in_bytes']
    inventory_path=BASE/(name+'.files.json');inventory=read(inventory_path)
    assert len(inventory)==i['extractedFileCount'] and sum(x['bytes'] for x in inventory)==i['extractedBytes']
    assert all((BASE/name/x['path']).is_file() and (BASE/name/x['path']).stat().st_size==x['bytes'] for x in inventory)
    artifacts.append({'name':name,'artifactId':i['artifactId'],'originalArchive':r,'apiDigest':a['digest'],'apiBytes':a['size_in_bytes'],'zipDigestAndSizeReverifiedAtFreeze':True,'extractedFileCount':len(inventory),'extractedBytes':sum(x['bytes'] for x in inventory),'extractedSizeAndExistenceReverifiedAtFreeze':True,'extractedSha256Inventory':record(inventory_path),'originalIntegrityReceipt':record(integrity_path)})
logs=[]
for job in jobs:
    p=BASE/('job-'+str(job['id'])+'.log');r=record(p);collected=read(BASE/('job-'+str(job['id'])+'.collected.json'))
    assert r['sha256']==collected['sha256'] and r['bytes']==collected['bytes'] and collected['headSha']==HEAD
    logs.append({'jobId':job['id'],'name':job['name'],'status':job['status'],'conclusion':job['conclusion'],'failedSteps':[s['name'] for s in job['steps'] if s['conclusion']=='failure'],'originalLog':r,'collectionReceipt':record(BASE/('job-'+str(job['id'])+'.collected.json'))})
assert len(logs)==5 and Counter(j['conclusion'] for j in jobs)==Counter({'success':3,'failure':2})
producer=read(BASE/'producer-input-evidence-summary.json');retained=read(BASE/'retained-attachment-evidence-summary.json');authority=read(BASE/'authority-attachment-evidence-summary.json');native_logs=read(BASE/'native-log-evidence-summary.json')
assert all(c['passed'] for c in producer['checks']) and all(c['passed'] for c in retained['checks'])
assert retained['attachmentCount']==94 and retained['xcresultHashMatchedAttachments']==94 and authority['attachmentCount']==421 and authority['xcresultHashMatchedAttachments']==421
case_overviews=[]
for kind,audit in [('retained',retained),('authority',authority)]:
    for t in audit['tests']:
        case={'host':kind,'identifier':t['identifier'],'result':t['result'],'durationSeconds':t['duration'],'issues':t['issues'],'attachmentCount':t['attachmentCount']}
        if kind=='retained':
            case.update(independentlyVerifiedScope=t['independentlyVerifiedScope'],dormantIntervalDurationsSeconds=[x['verifiedDurationSeconds'] for x in t['dormantIntervals']],runID=t['runID'],applicationJournal=t['applicationJournal'])
        else:
            case.update(independentChecks=t['independentChecks'],actualGeometryByAction=t['geometryByAction'])
        case_overviews.append(case)
assert Counter(t['result'] for t in case_overviews)==Counter({'Success':4,'Failure':4})
source_archive=read(BASE/'source-archive.json');source_path=Path(source_archive['archivePath']);source_record=record(source_path)
assert source_record['sha256']==source_archive['sha256'] and source_record['bytes']==source_archive['bytes'] and source_archive['headSha']==HEAD
receipts_names=['collection-contract.json','collector-process.json','collection-complete.json','last-run-status.json','last-jobs-status.json','artifacts.json','source-archive.json','source-delta-from-34460468965.json','producer-input-evidence-summary.json','retained-preservation-audit.json','retained-input-evidence-summary.json','retained-package-evidence-summary.json','retained-package-initial-audit-correction.json','retained-attachment-evidence-summary.json','authority-package-evidence-summary.json','authority-attachment-evidence-summary.json','native-log-evidence-summary.json']
receipts=[record(BASE/name) for name in receipts_names]
script_paths=[Path('/tmp/partydeck-engine-ci')/name for name in ['monitor-ios-hosts-34464316979.py','fetch-godot-comparison-source.py','decode-xcresult.py','audit-ios-host-producers.py','audit-ios-authority-34464316979.py','audit-ios-retained-inputs-34464316979.py','audit-ios-retained-package-34464316979.py','audit-ios-retained-attachments-34464316979.py','audit-ios-logs-34464316979.py','freeze-ios-evidence-34464316979.py']]
tools_dir=BASE/'audit-tools';tools_dir.mkdir(exist_ok=False);tool_receipts=[]
for path in script_paths:
    target=tools_dir/path.name
    with target.open('xb') as f:f.write(path.read_bytes())
    tool_receipts.append({'originalToolPath':str(path),**record(target)})
assert digest(tools_dir/'monitor-ios-hosts-34464316979.py')==read(BASE/'collector-process.json')['collectorSha256']
format_receipts=[record(p) for p in sorted((BASE/'research/macho').iterdir()) if p.is_file()]
summary={'schemaVersion':1,'runId':34464316979,'headSha':HEAD,'attempt':1,'workflow':run['path'],'workflowUrl':run['html_url'],'event':run['event'],'conclusion':run['conclusion'],'expectedInputs':{'host':'both','retained_stage':'test'},'verifiedInputsEvidence':record(BASE/'retained-input-evidence-summary.json'),'collectedAtUtc':complete['completedAtUtc'],'frozenAtUtc':datetime.now(timezone.utc).isoformat(),'collectorScope':'Read-only GitHub/API/archive/source collection and independent evidence audits; no dispatch, builds, source changes or Git integration.','sourceArchive':source_record,'artifactCount':len(artifacts),'artifacts':artifacts,'extractedFileCount':sum(x['extractedFileCount'] for x in artifacts),'extractedBytes':sum(x['extractedBytes'] for x in artifacts),'jobLogs':logs,'producerAuditCheckCount':len(producer['checks']),'retainedInputAuditCheckCount':len(read(BASE/'retained-input-evidence-summary.json')['checks']),'retainedPackageAuditCheckCount':len(read(BASE/'retained-package-evidence-summary.json')['checks']),'retainedAttachmentAuditCheckCount':len(retained['checks']),'rendererPackSha256':producer['pack']['sha256'],'nativeModuleSnapshotSha256':producer['moduleSnapshotSha256'],'nativeTestResults':case_overviews,'nativeTestCounts':dict(Counter(t['result'] for t in case_overviews)),'originalXcresultMatchedAttachments':515,'retainedAttachmentCounts':{'total':94,'pngs':retained['pngCount'],'measurements':retained['measurementCount'],'touchCandidates':retained['touchCandidateCount'],'dormantIntervals':retained['dormantIntervalCount']},'authorityAttachmentCounts':{'total':421,'pngs':authority['pngCount'],'measurements':authority['jsonMeasurementCount'],'actualTouchGeometries':authority['jsonTouchGeometryCount'],'observedControls':authority['jsonObservedControlCount']},'nativeLogSummary':[{'host':h['host'],'severityCounts':h['nativeSeverityCounts'],'classificationCounts':h['nativeClassificationCounts'],'genericXctestRestartMessages':len(h['xctestGenericRestartLines']),'cleanNativeLogClaim':False,'noCrashClaim':False} for h in native_logs['hosts']],'qualification':{'retainedEngineLifecycleQualified':False,'sameProcessReentryQualified':False,'allAuthorityGameplayCasesQualified':False,'kmpFactoryQualified':False,'deviceMetalQualified':False,'physicalMotionShutdownQualified':False,'realAudioInterruptionQualified':False,'simulatorRuntimeExecuted':True},'receiptIndex':receipts,'preservedAuditorScripts':tool_receipts,'binaryFormatSources':format_receipts,'limitations':['Both native hosts built and executed; retained passed two of three cases and Authority passed two of five. Neither full suite is qualified.','The failed retained case reaches the second 3D entry but fails while waiting for current diagnostics; its old-handle probe and later play/exit were not executed.','A passed repeated-entry case supports its measured one-process retention observations; the formal same-process qualification remains false because the required suite failed.','The Authority build result was recorded before tests and keeps false runtime qualification flags; observed case results here come from the original XCResult and correlated test logs.','Dormant interval audit verifies original endpoint measurements, monotonic counters and reported sample count; it does not reconstruct every intermediate AX read.','Retained touch-candidate attachments precede the final input check and are not treated as actual tap counts.','Actual Home is evidenced by SpringBoard/dock accessibility and native lifecycle callbacks; raw application state values are preserved even when they still report foreground.','Exported scripts are .gdc plus .gd.remap. Source fingerprints, pack entries and producer/consumer PCK byte identity are audited; literal source equality is not established by reverse-decoding bytecode.','Two top-level staged native archive files are absent from retained preservation. Their CI receipts match original preserved producer archives; independent rereads of those absent staged paths are not claimed.','Native unsupported-mouse errors, texture conversion warnings and two generic XCTest restart messages remain recorded; no clean-log or no-crash conclusion is claimed.','Visual review and source failure diagnoses are separate owner supplements; frozen source and observation receipts are not rewritten by later proposals.']}
output=BASE/'collection-evidence-summary.json';write_new(output,summary)
freeze={'schemaVersion':1,'runId':34464316979,'headSha':HEAD,'attempt':1,'frozenAtUtc':summary['frozenAtUtc'],'conclusion':'failure','frozenSummary':record(output),'receiptIndex':receipts,'artifactOriginals':[{'name':a['name'],'artifactId':a['artifactId'],**a['originalArchive']} for a in artifacts],'preservedAuditorScripts':tool_receipts,'policy':'Preserve these receipts and original artifacts unchanged. Add corrections or later diagnoses as separately hashed successors/supplements.','qualification':summary['qualification']}
frozen_path=BASE/'collection-evidence-frozen.json';write_new(frozen_path,freeze)
print(json.dumps({'frozen':record(frozen_path),'summary':record(output),'originalZipCount':len(artifacts),'extractedFileCount':summary['extractedFileCount'],'jobLogCount':len(logs),'matchedAttachments':515,'caseCounts':summary['nativeTestCounts']},indent=2),flush=True)
