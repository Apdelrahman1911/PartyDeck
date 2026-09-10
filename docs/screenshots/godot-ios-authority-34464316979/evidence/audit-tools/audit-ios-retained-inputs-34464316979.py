"""Correlate retained CI inputs and package using completed producer audit; no native execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import tarfile
BASE = Path('/tmp/partydeck-engine-ci/34464316979')
HEAD = 'ea84bf49e799675c181545cc3511460b11e0e23d'
SOURCE = BASE / 'source-ea84bf4'
HOST = SOURCE / 'godot/ios-host'
RETAINED = BASE / 'godot-ios-retained-host-test-attempt-1'
PRESERVED = BASE / 'retained-preserved'
ENGINE = BASE / 'godot-ios-host-engine'
FRAMEWORK = BASE / 'godot-ios-host-framework'
RENDERER = BASE / 'godot-ios-host-renderer'
checks = []
def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def file_receipt(path): return {'sha256': digest(path), 'bytes': path.stat().st_size}
def record(path): return {'path': str(path), **file_receipt(path)}
def sha(data): return hashlib.sha256(data).hexdigest()
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label

def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')

producer = read(BASE / 'producer-input-evidence-summary.json')
check('completed producer audit at exact revision', producer['runId'] == 34464316979 and producer['headSha'] == HEAD and all(c['passed'] for c in producer['checks']))
run = read(BASE / 'last-run-status.json')
jobs = read(BASE / 'last-jobs-status.json')['jobs']
check('exact completed run/head/event/attempt', run['id'] == 34464316979 and run['head_sha'] == HEAD and run['event'] == 'workflow_dispatch' and run['run_attempt'] == 1 and run['status'] == 'completed')
context = read(RETAINED / 'evidence/retained-ci-context.json')
check('retained CI exact revision, workflow revision, stage, run and architecture', context['source_commit'] == context['expected_source_commit'] == context['workflow_sha'] == HEAD and context['requested_stage'] == 'test' and context['run_id'] == '34464316979' and context['run_attempt'] == '1' and context['system'] == 'Darwin' and context['machine'] == 'arm64')
workflow = (SOURCE / '.github/workflows/godot-ios-authority-host.yml').read_text()
consumer_jobs = [job for job in jobs if job['id'] in (102830281362, 102830281410)]
check('archived workflow and both executed consumers identify host=both', "if: ${{ inputs.host != 'retained' }}" in workflow and "if: ${{ inputs.host == 'retained' || inputs.host == 'both' }}" in workflow and len(consumer_jobs) == 2 and all(job['conclusion'] != 'skipped' for job in consumer_jobs))
check('consumers use distinct hosted runners', len({job['runner_id'] for job in consumer_jobs}) == 2)
engine = read(ENGINE / 'evidence/engine-artifact.json')
framework = read(FRAMEWORK / 'evidence/authority-framework-result.json')
input_copies = []
for name, producer in [('engine', ENGINE), ('framework', FRAMEWORK), ('renderer', RENDERER)]:
    for path in sorted(producer.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(producer)
        copy = PRESERVED / 'retained-inputs' / name / relative
        check('retained original producer file: ' + name + '/' + relative.as_posix(),
              copy.is_file() and file_receipt(copy) == file_receipt(path))
        input_copies.append(name + '/' + relative.as_posix())
retained_inputs = read(RETAINED / 'retained-host-test/evidence/inputs.json')
result = read(RETAINED / 'retained-host-test/evidence/result.json')
check('retained source hashes unchanged during native build and test invocation', retained_inputs['sources'] == result['source_hashes_after'])
for name, expected in retained_inputs['sources'].items():
    check('retained harness matches exact archived source: ' + name, digest(HOST / name) == expected)
verified = retained_inputs['verified_engine_framework_pack']
check('retained nested engine/framework inputs match independent producer bytes',
      verified['engine_receipt'] == engine and verified['framework_receipt'] == framework)
check('retained staged input receipt equals runner input', verified == read(PRESERVED / 'evidence/authority-host-inputs.json'))
check('retained framework receipt bytes match producer', verified['framework_receipt_file']
      == file_receipt(FRAMEWORK / 'evidence/authority-framework-result.json'))
resources = read(PRESERVED / 'evidence/host-resources.json')
check('retained resources nested receipt', verified['resources'] == resources)
check('retained bundled PCK bytes match audited producer', file_receipt(PRESERVED / 'host-resources/ProbeResources/partydeck-last-light.pck')
      == file_receipt(RENDERER / 'partydeck-last-light.pck') == resources['optional_shared_pack'])
check('retained bundled PCK companion receipt matches producer', file_receipt(PRESERVED / 'host-resources/ProbeResources/partydeck-last-light.receipt.json')
      == file_receipt(RENDERER / 'partydeck-last-light.receipt.json'))
for name, expected in resources['diagnostic_sources'].items():
    check('retained diagnostic resource: ' + name, digest(PRESERVED / 'host-resources' / name) == expected)
for name, expected in resources['license_bundle_sha256'].items():
    check('retained license: ' + name, digest(PRESERVED / 'host-resources/ProbeResources/Licenses' / name) == expected)
check('retained fixture and manifest bytes', digest(PRESERVED / 'host-resources/ProbeResources/Launch.json') == resources['fixture_sha256']
      and digest(PRESERVED / 'host-resources/ProbeResources/fixture-manifest.json') == resources['fixture_manifest_sha256'])
ci_inputs = read(RETAINED / 'evidence/retained-ci-inputs.json')
direct_receipt_files, staged_receipt_files = [], []
for item in ci_inputs['files']:
    relative = Path(item['path']).relative_to('godot/ios-host/build')
    candidate = PRESERVED / relative
    if not candidate.is_file() and relative.parts[0] == 'artifacts':
        candidate = ENGINE / relative
        staged_receipt_files.append(relative.as_posix())
    else:
        direct_receipt_files.append(relative.as_posix())
    check('CI input file receipt: ' + relative.as_posix(), file_receipt(candidate)
          == {key: item[key] for key in ('sha256', 'bytes')})

check('result embeds original inputs and exact file digest', result['inputs'] == retained_inputs and result['inputs_file_sha256'] == digest(RETAINED / 'retained-host-test/evidence/inputs.json'))
check('retained build and linkage succeeded', result['swift_harness_compiled'] is True and result['native_and_kotlin_owners_linked'] is True and '** BUILD SUCCEEDED **' in (RETAINED / 'retained-host-test/evidence/build.log').read_text())
check('failed native test invocation preserves unqualified suite result', result['command_exit_code'] == 65 and len(result['native_tests_started']) == 3 and len(result['native_tests']) == 3 and all(result[k] is False for k in ['retained_engine_lifecycle_qualified','same_process_reentry_qualified','kmp_factory_qualified','device_metal_qualified','physical_motion_shutdown_qualified','real_audio_interruption_qualified']) and result['simulator_only'] is True)
check('XCResult and both successful exports preserved', result['test_evidence']['xcresult_retained'] is True and result['test_evidence']['export_commands'] == {'attachments_export_exit_code':0,'summary_export_exit_code':0})
check('summary and export metadata receipt hashes', result['test_evidence']['summary_sha256'] == digest(RETAINED / 'retained-host-test/evidence/test-summary.json') and result['test_evidence']['export_metadata_sha256'] == digest(RETAINED / 'retained-host-test/evidence/test-evidence-export.json'))
check('application observation file inventory', result['application_observation_files'] == sorted(p.name for p in (RETAINED / 'retained-host-test/evidence/application-observations').glob('*.json')))
summary = {'runId':34464316979,'headSha':HEAD,'attempt':1,'scope':'Exact-source consumer input and preservation correlation. Individual XCTest cases are evaluated separately; the retained suite remains failed.', 'producerAudit':record(BASE / 'producer-input-evidence-summary.json'),'sourceArchive':record(BASE / 'source-archive.json'),'workflowInputs':{'host':'both','hostEvidence':'Both consumers executed under the exact archived workflow conditions.','retained_stage':'test','context':record(RETAINED / 'evidence/retained-ci-context.json')},'consumerRunners':[{'jobId':j['id'],'runnerId':j['runner_id'],'name':j['name']} for j in consumer_jobs], 'preservationAudit':record(BASE / 'retained-preservation-audit.json'),'originalProducerFilesInPreservationVerified':input_copies,'ciReceiptFilesDirectlyVerifiedFromPreservation':direct_receipt_files,'ciStagedArchiveReceiptsCorrelatedWithProducer':staged_receipt_files,'stagedArchiveLimit':'Top-level staged native archives are absent from the preservation tar. Their CI receipts match original producer archives; no independent reread of absent staged files is claimed.','retainedSourceHashes':retained_inputs['sources'],'checks':checks}
write_new(BASE / 'retained-input-evidence-summary.json',summary)
print(json.dumps({'inputAudit':record(BASE / 'retained-input-evidence-summary.json'),'checksPassed':len(checks)}),flush=True)

package_checks=[]
def package_check(label, condition):
    package_checks.append({'check':label,'passed':bool(condition)})
    assert condition,label
archive=RETAINED / 'retained-host-test/artifacts/RetainedHost-simulator.app.tar.gz'
with tarfile.open(archive,'r:gz') as package:
    members={m.name:package.extractfile(m).read() for m in package.getmembers() if m.isfile()}
files=[{'member':name,'bytes':len(data),'sha256':sha(data)} for name,data in members.items()]
exe=members['RetainedHost.app/RetainedHost']
package_check('linked executable hash equals original result',sha(exe)==result['executable_sha256'])
magic,cpu,subtype,filetype,commands,command_bytes,flags,reserved=struct.unpack_from('<IiiIIIII',exe)
package_check('64-bit ARM64 executable header',magic==0xfeedfacf and cpu==0x100000c and filetype==2)
offset=32
uuid=None
versions=[]
symtab=None
for _ in range(commands):
    cmd,size=struct.unpack_from('<II',exe,offset)
    assert size>=8 and offset+size<=len(exe)
    if cmd==0x1b: uuid=exe[offset+8:offset+24].hex()
    if cmd==0x32:
        platform,minos,sdk=struct.unpack_from('<III',exe,offset+8)
        versions.append({'platform':platform,'minos':minos,'sdk':sdk})
    if cmd==0x2: symtab=struct.unpack_from('<IIII',exe,offset+8)
    offset+=size
package_check('Mach-O UUID and iOS Simulator SDK load command',uuid and any(v['platform']==7 and v['sdk']==0x1a0400 for v in versions))
package_check('complete load command boundary',offset==32+command_bytes)
expected_symbols=['_main','_OBJC_CLASS_$_PDGodotEngineOwner','_OBJC_CLASS_$_PDGodotPresentation','_OBJC_CLASS_$_PDGBIosQualificationFactory','_OBJC_CLASS_$_PDGBIosQualificationAuthority']
assert symtab
symoff,nsyms,stroff,strsize=symtab
assert symoff+16*nsyms<=len(exe) and stroff+strsize<=len(exe)
strings=exe[stroff:stroff+strsize]
matched_symbols=[]
for index in range(nsyms):
    strx,ntype,nsect,desc,value=struct.unpack_from('<IBBHQ',exe,symoff+index*16)
    assert strx<strsize
    stop=strings.find(b'\0',strx)
    name=strings[strx:stop].decode(errors='replace')
    if name in expected_symbols:
        matched_symbols.append({'name':name,'type':ntype,'section':nsect,'value':value})
package_check('all five required native/Kotlin owner symbols are defined in linked executable',len(matched_symbols)==len(expected_symbols) and {s['name'] for s in matched_symbols}==set(expected_symbols) and all(s['type']&0x0e==0x0e and s['section']>0 and s['value']>0 for s in matched_symbols))
symbols_log=(RETAINED / 'retained-host-test/evidence/symbols.log').read_text()
package_check('required symbols also present in original nm output',all(re.search(r'(?m)^.*\s'+re.escape(name)+r'$',symbols_log) for name in expected_symbols))
plist=plistlib.loads(members['RetainedHost.app/Info.plist'])
package_check('Simulator bundle and Xcode build identity',plist['CFBundleSupportedPlatforms']==['iPhoneSimulator'] and plist['DTXcodeBuild']=='17E202' and plist['CFBundleExecutable']=='RetainedHost')
pack=members['RetainedHost.app/ProbeResources/partydeck-last-light.pck']
package_check('bundled PCK matches audited producer and staged resource',sha(pack)==digest(RENDERER/'partydeck-last-light.pck')==resources['optional_shared_pack']['sha256'] and len(pack)==resources['optional_shared_pack']['bytes'])
package_check('bundled companion receipt equals exact producer bytes',sha(members['RetainedHost.app/ProbeResources/partydeck-last-light.receipt.json'])==digest(RENDERER/'partydeck-last-light.receipt.json'))
package_check('bundled fixture and manifest',sha(members['RetainedHost.app/ProbeResources/Launch.json'])==resources['fixture_sha256'] and sha(members['RetainedHost.app/ProbeResources/fixture-manifest.json'])==resources['fixture_manifest_sha256'])
for name,expected in resources['license_bundle_sha256'].items(): package_check('bundled license '+name,sha(members['RetainedHost.app/ProbeResources/Licenses/'+name])==expected)
package_summary={'runId':34464316979,'headSha':HEAD,'scope':'Linked app package and static symbol identity only. No app was executed during this audit.','archive':record(archive),'fileCount':len(files),'files':files,'executable':{'bytes':len(exe),'sha256':sha(exe),'machOUuid':uuid,'cpuType':cpu,'fileType':filetype,'buildVersions':versions,'symbolTableEntries':nsyms,'requiredDefinedSymbols':matched_symbols},'plist':plist,'packSha256':sha(pack),'inputAudit':record(BASE/'retained-input-evidence-summary.json'),'originalSymbolLog':record(RETAINED/'retained-host-test/evidence/symbols.log'),'checks':package_checks}
write_new(BASE/'retained-package-evidence-summary.json',package_summary)
print(json.dumps({'packageAudit':record(BASE/'retained-package-evidence-summary.json'),'checksPassed':len(package_checks),'executableSha256':sha(exe)}),flush=True)
