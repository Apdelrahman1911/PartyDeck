"""Preserve severity-tagged native output and XCTest failures without a no-crash inference."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
BASE=Path('/tmp/partydeck-engine-ci/34464316979')
STORE=Path('/root/projects/PartyDeck/artifacts/evidence-storage')
HEAD='ea84bf49e799675c181545cc3511460b11e0e23d'
def read(path):return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def record(path):return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)}
def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
pattern=re.compile(r'\[ERROR\]|\[WARNING\]|\bSCRIPT ERROR:|\bERROR:|\bfatal error:|\bEXC_BAD_ACCESS\b|\bSIGABRT\b|\bterminating app\b|\buncaught exception\b')
hosts=[]
for kind,folder,job_id in [('retained','34464316979-retained-xcresult-decoded',102830281362),('authority','34464316979-xcresult-decoded',102830281410)]:
    decoded=STORE/folder;index=read(decoded/'decoded-object-index.json');streams=[];events=[]
    for stream in index['appStreams']:
        p=Path(stream['appOutputLog']);assert digest(p)==stream['decodedSha256']
        streams.append({**record(p),'originalObject':stream['source'],'originalObjectSha256':stream['sourceSha256'],'zstdDecoded':stream['zstdDecoded']})
        with p.open('rb') as f:
            for number,raw in enumerate(f,1):
                text=raw.decode(errors='replace').rstrip('\r\n')
                if not pattern.search(text):continue
                match=re.search(r'(RetainedHost|AuthorityHost)\[(\d+):(\d+)\] \[(ERROR|WARNING)\]',text)
                severity=match[4] if match else 'other_severity_candidate'
                classification='unsupported_mouse_display_server_error' if 'mouse_get_position(): Mouse is not supported' in text else 'rgba_float_to_half_conversion_warning' if 'Image format RGBAFloat not supported by hardware, converting to RGBAHalf' in text else 'other'
                events.append({'stream':str(p),'line':number,'rawLineSha256':hashlib.sha256(raw).hexdigest(),'text':text,'severity':severity,'classification':classification,'processIdentifier':int(match[2]) if match else None,'threadIdentifier':int(match[3]) if match else None})
    log=BASE/('job-'+str(job_id)+'.log');lines=log.read_bytes().splitlines(keepends=True)
    restarts=[];failures=[];cases=[]
    for number,raw in enumerate(lines,1):
        text=raw.decode(errors='replace').rstrip('\r\n')
        line_record={'line':number,'rawLineSha256':hashlib.sha256(raw).hexdigest(),'text':text}
        if 'Restarting after unexpected exit, crash, or test timeout' in text:restarts.append(line_record)
        if re.search(r'\.swift:\d+: error:',text):failures.append(line_record)
        if re.search(r"Test Case '.+' (started|passed|failed)",text):cases.append(line_record)
    per_process=[]
    for pid in sorted({x['processIdentifier'] for x in events if x['processIdentifier']}):
        selected=[x for x in events if x['processIdentifier']==pid]
        per_process.append({'processIdentifier':pid,'countsBySeverity':dict(Counter(x['severity'] for x in selected)),'countsByClassification':dict(Counter(x['classification'] for x in selected))})
    hosts.append({'host':kind,'appOutputStreams':streams,'decodedObjectIndex':record(decoded/'decoded-object-index.json'),'nativeSeverityCounts':dict(Counter(x['severity'] for x in events)),'nativeClassificationCounts':dict(Counter(x['classification'] for x in events)),'perProcess':per_process,'nativeLogEvents':events,'jobLog':record(log),'xctestCaseEvents':cases,'xctestFailureLines':failures,'xctestGenericRestartLines':restarts,'decoderCrashSignatureCandidateCount':len(index['crashCandidates']),'cleanNativeLogClaim':False,'noCrashClaim':False})
summary={'runId':34464316979,'headSha':HEAD,'scope':'Exact preserved severity-tagged output with raw line hashes and original XCResult object provenance. Generic XCTest restart messages are preserved as ambiguous; absent decoder crash signatures do not establish absence of a crash. The chosen scan is not a complete semantic audit of all platform output.','pattern':pattern.pattern,'patternIsCaseSensitive':True,'hosts':hosts,'cleanNativeLogClaim':False,'noCrashClaim':False}
output=BASE/'native-log-evidence-summary.json';write_new(output,summary)
print(json.dumps({'receipt':record(output),'hosts':[{'host':h['host'],'nativeSeverityCounts':h['nativeSeverityCounts'],'nativeClassificationCounts':h['nativeClassificationCounts'],'genericRestartMessages':len(h['xctestGenericRestartLines']),'xctestFailureCount':len(h['xctestFailureLines'])} for h in hosts]}),flush=True)
