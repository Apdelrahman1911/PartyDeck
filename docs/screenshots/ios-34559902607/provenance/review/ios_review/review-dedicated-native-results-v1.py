"""Independent bounded reconciliation of current dedicated originals and behavior."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shlex

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage')
BASE = ROOT / '34559902607'
OWN = ROOT / 'restart-20260911T0457/ios_review'
ARTIFACT = 'ios-reports-and-simulator-app'
FILES = BASE / ARTIFACT
HEAD = '39405bb0fd6ba0214e70ed251aab1f9f571dc9aa'
IDENTITY = (34559902607, HEAD, 1)
CHECKS = []

def require(value, label):
    if not value:
        raise AssertionError(label)
    CHECKS.append(label)

def record(path):
    size, digest = 0, hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):
            size += len(part); digest.update(part)
    return dict(path=str(path), bytes=size, sha256=digest.hexdigest())

def pinned(path, sha):
    value = record(path)
    require(value['sha256'] == sha, 'Pinned file: ' + path.name)
    return value

def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'No duplicate JSON keys')
        value[key] = item
    return value

def read(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)

def run_identity(value):
    return tuple(value[key] for key in ('runId','headSha','attempt'))

owners = {}
owner_records = {}
execution_records = []
for name, filename, sha, execution_sha in [
    ('ordinary-uikit','ordinary-and-uikit-outcomes-v1.json','9409c5f218a7b2570693e38839d6f2d1bcb550585815514be48df68448084bb5','653edbf9a857693f3421acba97290e868615a2d6c1edb5427cb72a90dbb902c9'),
    ('production','production-session-outcome-v1.json','03a2bf55ea8f9351b7eab0ce3ad2035c4656d78ffe01b3e538d19ff9f6aab956','c160d32a4ff5e418126d09985077cf21adf7259b5105f78a56e4378db65c3f4a'),
]:
    owner_records[name] = pinned(BASE / filename,sha)
    owner = read(BASE / filename)
    require(run_identity(owner) == IDENTITY,'Owner result run identity')
    owners[name] = owner
    execution_path = BASE / ('audit-executions/' + name + '-v1.execution.json')
    execution_record = pinned(execution_path,execution_sha)
    execution_records.append(execution_record)
    execution = read(execution_path)
    require(run_identity(execution) == IDENTITY and execution['exitCode'] == 0,'Successful exact owner execution')
    require(execution['auditor'] == owner['auditor'] and record(Path(execution['auditor']['path'])) == execution['auditor'],
            'Owner ran exact reviewed auditor bytes')
    require(record(Path(execution['sourceApproval']['path'])) == execution['sourceApproval'], 'Owner execution binds independent source approval')
    for stream in ('stdout','stderr'):
        require(record(Path(execution[stream]['path'])) == execution[stream], 'Owner execution stream pin')
    require(execution['stderr']['bytes'] == 0,'Owner execution empty stderr')
ordinary_owner, production_owner = owners['ordinary-uikit'], owners['production']

prior_path = OWN / 'native-log-independent-review-v1.json'
prior_record = pinned(prior_path,'9ef77741a7f7cb60361a8885fdcb9e2b655ae7c752bb81751f06665774dcd94f')
prior = read(prior_path)
require(production_owner['originalNativeJobLog'] == prior['originalLog'], 'Original job log reuses independently verified prior pin without rehash')
early_path = BASE / 'completed-native-job-log-outcomes-v1.json'
early_record = pinned(early_path,'6db6b4106b437f663db3d9ce172f6fd7d82f0c4c57a0c730e66e63d311bda5af')
early = read(early_path)
require(run_identity(early) == IDENTITY,'Early named outcome exact run')
require(early_record == prior['reviewedOutcome'], 'Early outcome matches independent prior review')

inventory_path = BASE / (ARTIFACT + '.files.json')
inventory_record = record(inventory_path)
require(inventory_record == ordinary_owner['originalMemberInventory'] == production_owner['originalMemberInventory'], 'Both owners bind same original inventory')
items = read(inventory_path)
inventory = {item['path']:item for item in items}
require(len(inventory) == len(items), 'Unique original member inventory')
integrity_path = BASE / (ARTIFACT + '.integrity.json')
integrity_record = pinned(integrity_path,'9d84e127bff0d0bd146ca5202c4c5f11785e2aa904878257e97262000932c75b')
require(integrity_record == ordinary_owner['originalArtifactIntegrity'] == production_owner['originalArchiveIntegrity'], 'Both owners bind same archive integrity report')
integrity = read(integrity_path)
require(run_identity(integrity) == IDENTITY and integrity['name'] == ARTIFACT,'Original artifact exact run and name')
require(integrity['completeOriginalArchivePreserved'] and integrity['allZipMembersStreamHashedAndCRCVerified']
        and integrity['zipDigestMatchesApi'] and integrity['zipSizeMatchesApi'], 'Attributed complete archive verification is successful')
originals = {}

def original(relative):
    if relative in originals:
        return originals[relative]
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts,'Safe original member path')
    item = inventory[relative]
    require(item['retainedExtracted'] is True,'Original member retained extracted')
    actual = record(FILES / relative)
    require(all(actual[key] == item[key] for key in ('bytes','sha256')),'Actual original bytes match member inventory: ' + relative)
    originals[relative] = actual
    return actual

def document(relative):
    original(relative)
    return read(FILES / relative)

def compare_pointer(pointer, relative):
    expected = original(relative)
    require(all(pointer[key] == expected[key] for key in ('path','bytes','sha256')),'Owner original pointer byte identity')
    require(pointer.get('archiveMember',relative) == relative and pointer.get('retainedExtracted',True) is True,'Owner pointer original member identity')

case_line = re.compile(r"^Test Case '-\[(?P<class>[^ ]+) (?P<method>[^\]]+)\]' (?:(?P<start>started)\.|(?P<status>passed|failed|skipped) \((?P<seconds>[0-9]+(?:\.[0-9]+)?) seconds\)\.)$")
logs = {}
for scope, relative in [('ordinary','build/ci/ios/xcodebuild.log'),('uikit-layout','build/ci/ios/godot-layout/test.log'),('production-sessions','build/ci/ios/godot-session/test.log')]:
    text = (FILES / relative).read_text()
    original(relative)
    starts, ends, unsupported, success, failures = [], [], [], [], []
    for number, line in enumerate(text.splitlines(),1):
        if line.startswith('Test Case '):
            match = case_line.fullmatch(line)
            if not match:
                unsupported.append(number); continue
            name = match['class'] + '/' + match['method']
            if match['start']:
                starts.append(dict(case=name,line=number))
            else:
                ends.append(dict(case=name,line=number,status=match['status'],wallSecondsText=match['seconds']))
        if line == '** TEST SUCCEEDED **': success.append(number)
        if '** TEST FAILED **' in line or '** BUILD FAILED **' in line or re.search(r'PartyDeck[^\n]*\.swift:\d+[^\n]*error:',line):
            failures.append(number)
    expected = early['scopes'][scope]
    require(not unsupported and not failures and len(success) == 1, 'Dedicated log has exact parsable XCTest outcomes and one success marker')
    require([row['case'] for row in starts] == [row['case'] for row in expected['started']], 'Dedicated start sequence matches independently reviewed job log')
    normalized = [{k:row[k] for k in ('case','status','wallSecondsText')} for row in ends]
    require(normalized == [{k:row[k] for k in ('case','status','wallSecondsText')} for row in expected['finished']], 'Dedicated finish identity/status/duration matches job log')
    require(Counter(row['case'] for row in starts) == Counter(row['case'] for row in ends)
            and all(value == 1 for value in Counter(row['case'] for row in starts).values())
            and all(row['status'] == 'passed' for row in ends), 'Each dedicated case starts and passes exactly once')
    if scope in ('ordinary','uikit-layout'):
        owner_section = ordinary_owner['ordinary' if scope == 'ordinary' else 'uikitLayout']
        require(owner_section['cases'] == normalized, 'Owner ordinary/UIKit cases match independently parsed originals')
        compare_pointer(owner_section['originalLog'],relative)
    else:
        require(production_owner['started'] == [row['case'] for row in starts]
                and production_owner['finished'] == [dict(case=row['case'],status=row['status'],seconds=row['wallSecondsText']) for row in ends],
                'Owner production cases match independently parsed originals')
        compare_pointer(production_owner['originalTestLog'],relative)
    logs[scope] = dict(original=original(relative),started=starts,finished=ends,successMarkerLines=success,
                       eachExpectedCasePassedExactlyOnce=True,unparsedCaseLines=unsupported,sourceOrTestFailureLines=failures)

summaries = {}
settings = {}
for scope,prefix,expected_count,condition in [('uikit-layout','build/ci/ios/godot-layout/',3,'PARTYDECK_GODOT_SESSION_QUALIFICATION'),
                                          ('production-sessions','build/ci/ios/godot-session/',2,'PARTYDECK_GODOT_SESSION_QUALIFICATION')]:
    summary = document(prefix + 'test-summary.json')
    require(summary['result'] == 'Passed' and summary['passedTests'] == summary['totalTestCount'] == expected_count,
            'Original summary exact passed total')
    require(all(summary[key] == 0 for key in ('failedTests','skippedTests','expectedFailures')) and summary['testFailures'] == [],
            'Original summary has no failing/skipped/expected-failure tests')
    require(len(summary['devicesAndConfigurations']) == 1,'One original Simulator test configuration')
    device_config = summary['devicesAndConfigurations'][0]
    require(device_config['device']['platform'] == 'iOS Simulator' and device_config['device']['architecture'] == 'arm64',
            'Summary identifies actual arm64 Simulator execution')
    require(device_config['passedTests'] == expected_count and all(device_config[key] == 0 for key in ('failedTests','skippedTests','expectedFailures')),
            'Device/config summary counters match')
    if scope == 'uikit-layout': require(summary == ordinary_owner['uikitLayout']['summary'],'Original UIKit summary equals owner copy')
    else: require(summary == production_owner['originalSummary'],'Original production summary equals owner copy')
    build_settings = document(prefix + 'build-settings.json')
    targets = {item['target']:item['buildSettings'] for item in build_settings}
    expected_targets = {'PartyDeck','PartyDeckTests'} if scope == 'uikit-layout' else {'PartyDeck','PartyDeckUITests'}
    require(len(build_settings) == 2 and set(targets) == expected_targets,'Original build settings contain exact source-selected app/test targets')
    checked = {}
    for target in ('PartyDeck','PartyDeckTests') if scope == 'uikit-layout' else ('PartyDeck','PartyDeckUITests'):
        value = targets[target]
        conditions = shlex.split(value['SWIFT_ACTIVE_COMPILATION_CONDITIONS'])
        require({'DEBUG',condition} <= set(conditions),'Effective required qualification condition on app and applicable test target')
        require(value['CONFIGURATION'] == 'Debug' and value['PLATFORM_NAME'] == 'iphonesimulator', 'Effective Debug Simulator configuration')
        checked[target] = {key:value[key] for key in ('CONFIGURATION','PLATFORM_NAME','SWIFT_ACTIVE_COMPILATION_CONDITIONS')}
    settings[scope] = dict(original=original(prefix+'build-settings.json'),verifiedTargets=checked)
    summaries[scope] = dict(original=original(prefix+'test-summary.json'),summary=summary)

layout_gate = document('build/ci/ios/godot-layout/result.json')
layout_status = document('build/ci/ios/godot-layout/command-status.json')
require(layout_gate == ordinary_owner['uikitLayout']['gate'] and layout_status == layout_gate['command_status'], 'Original UIKit gate/status agree with owner')
require(layout_gate['source_revision'] == HEAD and layout_gate['command_exit'] == 0
        and layout_gate['problems'] == [] and layout_gate['native_layout_named_test_evidence_complete'] is True
        and layout_gate['production_engine_or_shipping_promotion'] is False, 'UIKit gate exact source, successful named evidence and bounded scope')
require(all(type(value) is int and value == 0 for value in layout_status.values()),'All original UIKit command/export status codes are zero')
require(layout_gate['started'] == [row['case'] for row in logs['uikit-layout']['started']]
        and layout_gate['finished'] == [dict(case=row['case'],status=row['status'],seconds=row['wallSecondsText']) for row in logs['uikit-layout']['finished']],
        'UIKit gate agrees with independently parsed named log outcomes')
source_root = ROOT / 'source-39405bb0-ios-scope-v2-7tdjsk4j/source-scope'
source_binding = read(source_root / 'source-run-binding-v1.json')
source_catalog = {item['sourcePath']:item for item in source_binding['selectedSourceFiles']}
for item in layout_gate['source_files']:
    if item['path'] == 'scripts/check-ios-godot-layout.py':
        require(item['sha256'] == 'b35ce76b04efded3c8726eb739fd574cc5cbaa0542ebe2c9ba863530311a4bf7','UIKit gate binds independently linked supplemental checker')
    else:
        require(item['sha256'] == source_catalog[item['path']]['sha256'],'UIKit gate source hash matches frozen selected-source binding')
require(len(layout_gate['source_files']) == 8, 'UIKit gate has eight source pins')
for item in layout_gate['evidence_files']:
    relative = 'build/ci/ios/' + item['path'].split('/build/ci/ios/',1)[1]
    require(original(relative)['sha256'] == item['sha256'],'UIKit gate original evidence file hash')
production_gate = document('build/ci/ios/godot-session/result.json')
production_exports = document('build/ci/ios/godot-session/test-evidence-export.json')
require(production_gate == production_owner['originalGateResult'] and production_exports == production_owner['originalExportExitCodes'], 'Original production gate/exports equal owner copies')
require(production_gate['command_exit'] == 0 and production_gate['problems'] == []
        and production_gate['named_test_evidence_complete'] is True
        and production_gate['native_acceptance_or_shipping_promotion'] is False,'Original production gate is successful bounded named evidence')
require(production_gate['started'] == production_owner['started'] and production_gate['finished'] == production_owner['finished'],'Original production gate exact named cases')
require(production_gate['test_log_sha256'] == original('build/ci/ios/godot-session/test.log')['sha256']
        and production_gate['test_summary_sha256'] == original('build/ci/ios/godot-session/test-summary.json')['sha256'], 'Production gate actual log/summary hashes')
require(set(production_exports) == {'attachments_export_exit_code','summary_export_exit_code'}
        and all(type(value) is int and value == 0 for value in production_exports.values()),'Original production export statuses zero')
for item in production_gate['attachments']:
    require(original('build/ci/ios/godot-session/attachments/' + item['path'])['sha256'] == item['sha256'], 'Production gate attachment hash joins actual original')
interop = document('build/ci/ios/interop/result.json')
orchestration = document('build/ci/ios/interop/orchestration.json')
require(orchestration == dict(passed=True,xcodeExitCode=0,nativeInteropTest='testSwiftAndJavaTLSInteroperabilityInBothDirections',javaExitCode=0),
        'Original Java/Swift orchestration successful and exact case')
require(interop == dict(version=1,status='PASS',forwardBytesReceived=65536,forwardBytesSent=20000,
                       reverseBytesSent=20000,reverseBytesReceived=65536,forwardTerminalState='Closed',reverseTerminalState='Closed'),
        'Original Java/Swift exchange exact byte counts and clean terminal closure')

schema_path = ROOT / 'restart-20260911T0457/ios_evidence/audit-tools/ios_current_attachment_schema_v1.py'
schema_record = pinned(schema_path,'fc9cea014f6996891fe643a0e97e9a337134d2192df20761192415b4c1b9d335')
schema = {'__name__':'independent_current_attachment_schema'}
exec(compile(schema_path.read_bytes(),'reviewed-pure-schema','exec'),schema)
manifest_records = []
attachment_index = []
observations = []
scrolls = []
captures = []
opaque_json = []
production_pointer_map = {item['original']['archiveMember']:item for item in
    production_owner['observationPointers'] + production_owner['capturePointers'] + production_owner['passiveBodyScrollEvidence']}
ordinary_pointer_map = {item['original']['archiveMember']:item for item in ordinary_owner['exportedAttachmentPointers']}
require(len(production_pointer_map) == 106 and len(ordinary_pointer_map) == 10,'Owner attachment indexes have unique current member identities')
for scope,prefix in [('ordinary','build/ci/ios/attachments/'),('uikit-layout','build/ci/ios/godot-layout/attachments/'),
                     ('production-sessions','build/ci/ios/godot-session/attachments/')]:
    manifest = document(prefix+'manifest.json')
    manifest_records.append(dict(scope=scope,original=original(prefix+'manifest.json'),cases=len(manifest)))
    seen, occurrence = set(), Counter()
    if scope == 'production-sessions':
        require(len(manifest) == 2 and {item['testIdentifier'] for item in manifest} ==
                {'PartyDeckGodotSessionUITests/testProduction2DPracticeSession()','PartyDeckGodotSessionUITests/testProduction3DPracticeSession()'},
                'Production manifest has exact two named case identities')
    elif scope == 'uikit-layout':
        require(manifest == [],'Original UIKit manifest contains no exported media')
    else:
        require({item['testIdentifier'].removesuffix('()') for item in manifest} ==
                {row['case'].removeprefix('PartyDeckUITests.') for row in logs['ordinary']['finished'] if row['case'].startswith('PartyDeckUITests.')},
                'Ordinary manifest identifies all three passing UI cases')
    for case_ordinal, case in enumerate(manifest,1):
        mode = ('2d' if '2D' in case['testIdentifier'] else '3d') if scope == 'production-sessions' else None
        require(case['testIdentifierURL'] == 'test://com.apple.xcode/PartyDeck/PartyDeckUITests/' + case['testIdentifier'].removesuffix('()'), 'Manifest URL exact named test identity')
        for ordinal, item in enumerate(case['attachments'],1):
            filename = item['exportedFileName']
            require(type(filename) is str and Path(filename).name == filename and filename not in ('','.','..') and filename not in seen,
                    'Unique safe original exported filename')
            seen.add(filename)
            require(item['isAssociatedWithFailure'] is False and type(item['timestamp']) in (float,int) and math.isfinite(item['timestamp']),
                    'Original attachment finite timestamp and no failure association')
            relative = prefix + filename
            pin = original(relative)
            pointer = (production_pointer_map if mode else ordinary_pointer_map)[relative]
            compare_pointer(pointer['original'],relative)
            require(pointer['testIdentifier'] == case['testIdentifier'] and pointer['manifestCaseOrdinal'] == case_ordinal
                    and pointer['caseAttachmentOrdinal'] == ordinal and pointer['exportMetadata'] == item,'Owner pointer preserves exact original case, ordinal and export metadata')
            label = schema['source_label'](item['suggestedHumanReadableName'],mode) if mode else None
            row = dict(scope=scope,caseMode=mode,testIdentifier=case['testIdentifier'],testIdentifierURL=case['testIdentifierURL'],
                       manifestCaseOrdinal=case_ordinal,caseAttachmentOrdinal=ordinal,original=pin,
                       sourceAttachmentKind=label[0] if label else None,sourceAttachmentName=label[1] if label else None,
                       exportMetadata=item)
            if label:
                occurrence[(case['testIdentifier'],*label)] += 1
                row['sameSourceLabelOccurrenceInManifest'] = occurrence[(case['testIdentifier'],*label)]
                require(all(pointer[key] == row[key] for key in ('sourceAttachmentKind','sourceAttachmentName','sameSourceLabelOccurrenceInManifest')),
                        'Owner preserves source label and occurrence within original manifest')
            attachment_index.append(row)
            suffix = Path(filename).suffix.lower()
            if suffix in ('.png','.jpg','.jpeg','.mp4','.mov'):
                captures.append(row)
            elif suffix == '.json':
                if label is None or label[0] not in ('observation','body-scroll'):
                    opaque_json.append(row); continue
                value = document(relative)
                require(pin['bytes'] <= 32768,'Source-named sanitized original within emitter size limit')
                if label[0] == 'observation':
                    schema['validate_observation'](value,mode)
                    require(pointer['observationSequence'] == value['observationSequence'] and pointer['validatedSanitizedSchemaAndContext'] is True,
                            'Owner observation sequence/schema assertion matches original')
                    for section in ('controller','port','native'):
                        raw = value['port'].get('native') if section == 'native' else value[section]
                        context = pointer['context'].get(section)
                        if context is not None:
                            require(type(raw) is dict and all(key in raw and raw[key] == field for key,field in context.items()),
                                    'Owner context preserves actual field presence, null and zero: ' + section)
                    observations.append({**row,'value':value})
                else:
                    schema['validate_body_scroll'](value,mode)
                    require(pointer['coverage'] == value,'Owner body-scroll coverage equals original')
                    scrolls.append({**row,'value':value})
    require(seen == {path.removeprefix(prefix) for path in inventory if path.startswith(prefix) and path != prefix+'manifest.json'},
            'Every original exported attachment is indexed exactly once')
require(len(observations) == 64 and len(scrolls) == 1 and len([row for row in captures if row['caseMode']]) == 41 and not opaque_json,
        'Actual production attachment types match observed owner counts without parsing unnamed JSON')

def ordered(rows):
    return sorted(rows,key=lambda item:(item['exportMetadata']['timestamp'], -item['caseAttachmentOrdinal']))

def refs(rows):
    return [{key:row[key] for key in ('testIdentifier','caseAttachmentOrdinal','sourceAttachmentName','original','exportMetadata')}
            | ({'observationSequence':row['value']['observationSequence']} if 'observationSequence' in row.get('value',{}) else {}) for row in rows]

def checkpoint(mode, name):
    values = ordered([row for row in observations if row['caseMode'] == mode and row['sourceAttachmentName'] == name])
    require(values,'Required actual source-named observation exists: ' + name)
    return values

def capture_observations(mode, tail):
    return checkpoint(mode,mode+' '+tail+' latest sanitized observation')

def live(value):
    c,p = value['controller'],value['port']; n,r,g = p['native'],p['renderer'],p['geometry']
    return all((p['active'], not p['closing'],p['portReadyConfirmed'],c['sessionPresent'],c['practice'],c['screen']=='SESSION',
        c['mode']=='GODOT_'+r['presentationMode'].upper(),c['lifecycle']=='ACTIVE',c['foreground'],not c['backgrounded'],not c['leaveConfirmation'],
        n['nativeForeground'],n['authorityForegroundGrant'],n['authorityReadyConfirmed'],n['inputViewEnabled'],n['renderLoopActive'],
        not n['privacyCoverVisible'],not n['dormant'],not n['emptyTree'],n['surfaceAttached'],g['surfaceAccessibilityHiddenByContainer'],
        g['engineAccessibilityHidden'],not g['outerCoverVisible'],r['foreground'],r['sceneStateApplied'],
        r['revision']==c['projectedRendererRevision'],c['sessionRevision'] is not None,c['sessionRevision']==c['projectedSessionRevision']))

def dormant(value):
    c,p=value['controller'],value['port']; n=p['native']
    return all((c['mode']=='COMPOSE',c['lifecycle']=='COMPOSE',not p['active'],not p['closing'],p['lastCloseSucceeded'] is True,
                n['dormant'],n['emptyTree'],not n['surfaceAttached'],not n['inputViewEnabled'],not n['nativeForeground'],
                not n['authorityForegroundGrant'],not n['renderLoopActive'],n['queuedCommands']==n['queuedEvents']==n['queuedBytes']==0))

def concealed(value):
    r=value['port']['renderer']
    return r['handConcealed'] and r['selectedCount']==r['privateFaceCount']==r['privateLabelCount']==0 and not any(x['selected'] for x in r['controls'])

def selected(value):
    r=value['port']['renderer']
    return not r['handConcealed'] and r['selectedCount']==1 and r['privateFaceCount']>0 and r['privateLabelCount']>0 and \
        [item['cardIndex'] for item in r['controls'] if item['group']=='partydeck_hand_card' and item['selected']]==[0]

def still(value, after):
    return all(value['port']['native'][key] == after['port']['native'][key]
               for key in ('nativePresentedFrames','iterations','drawCalls','queuedCommands','queuedEvents','queuedBytes'))

behaviors = []
capture_pairs = []
for mode in ('2d','3d'):
    actual = ordered([row for row in observations if row['caseMode']==mode])
    require(all(int(after['value']['observationSequence']) >= int(before['value']['observationSequence']) for before,after in zip(actual,actual[1:])),
            'Original chronological observation sequence never regresses: ' + mode)
    initial = capture_observations(mode,'production concealed entry')[0]
    baseline = initial['value']; baseline_c=baseline['controller']; baseline_n=baseline['port']['native']
    require(live(baseline) and concealed(baseline),'First native entry is live, Ready, foreground and concealed: ' + mode)
    standard = [capture_observations(mode,'Standard '+name)[0] for name in ('concealed','all five native card descriptions',
                'maximum selection and count-only feedback','Hide removes private nodes and selection','fresh Reveal is unselected')]
    for row in standard:
        c,p=row['value']['controller'],row['value']['port']
        require(c['sessionGeneration']==baseline_c['sessionGeneration'] and c['sessionRevision']==baseline_c['sessionRevision']
                and c['handCount']==5 and c['mode']=='COMPOSE' and c['ownTurn'] and c['canPlay']
                and c['lastViewerReceipt'] is None and not p['ownerCreated'] and p['native'] is None,
                'Original Standard hand checkpoint preserves authority revision and lazy engine ownership: ' + mode)
    for row in actual:
        n=row['value']['port'].get('native')
        if n is not None:
            require(n['bootstrapCount']==1 and n['processIdentifier']==baseline_n['processIdentifier']
                    and n['retainedEnginePolicy'] and n['retainedIdentitiesMatchFirstEntry'], 'Every native original retains one engine/process identity: ' + mode)
    selections=capture_observations(mode,'real native card selection')
    hides=capture_observations(mode,'Hide removes private faces labels and selection')
    require(len(selections)==len(hides)==2,'Initial and new-session selection/Hide occurrences are distinct: ' + mode)
    for selection,hide in zip(selections,hides):
        before,after=selection['value'],hide['value']
        require(live(before) and selected(before) and live(after) and concealed(after),'Actual select/Hide pair has required renderer private-state transition: ' + mode)
        require(before['controller']['sessionGeneration']==after['controller']['sessionGeneration']
                and before['port']['native']['presentationGeneration']==after['port']['native']['presentationGeneration']
                and before['port']['native']['intentEvents']==after['port']['native']['intentEvents'], 'Select/Hide preserves presentation and emits no authority intent: ' + mode)
    before_play=checkpoint(mode,mode+' measured play before actual coordinate tap')
    require(len(before_play)==1,'One original measured native Play tap: ' + mode)
    accepted=capture_observations(mode,'real authority accepted native Play')[0]
    a,b=accepted['value'],before_play[0]['value']; receipt=a['controller']['lastViewerReceipt']; old_receipt=b['controller'].get('lastViewerReceipt')
    require(live(a) and live(b) and selected(b) and receipt['accepted'] and receipt['error'] is None
            and receipt['action']=='PLAY_CARDS' and receipt['mode']=='GODOT_'+mode.upper()
            and receipt['sessionGeneration']==b['controller']['sessionGeneration']
            and receipt['presentationOrdinal']==b['controller']['presentationOrdinal']
            and receipt['expectedRevision']==b['controller']['sessionRevision']
            and int(receipt['revision'])>int(receipt['expectedRevision'])
            and int(receipt['serial'])==(int(old_receipt['serial']) if old_receipt else 0)+1
            and int(a['controller']['sessionRevision'])>=int(receipt['revision'])
            and a['port']['native']['intentEvents']==b['port']['native']['intentEvents']+1,
            'Actual native Play has one accepted, exact-context authority receipt and intent: ' + mode)
    require(a['controller']['handCount']==b['controller']['handCount']-1,'Actual native Play decreases observed hand count by one: ' + mode)
    returned=capture_observations(mode,'same session Standard return')[0]
    r=returned['value']
    require(dormant(r) and r['controller']['sessionGeneration']==baseline_c['sessionGeneration']
            and int(r['controller']['privacyEpoch'])>int(a['controller']['privacyEpoch'])
            and r['port']['renderer'] is None, 'Standard return retains same session with retired renderer and advanced privacy: ' + mode)
    standard_action_rows=ordered([row for row in actual if row['sourceAttachmentName'].startswith(mode+' real Standard authority accepted ')])
    require(len(standard_action_rows)==1,'One actual accepted Standard action checkpoint: ' + mode)
    standard_action=standard_action_rows[0]; s=standard_action['value']; sr=s['controller']['lastViewerReceipt']
    require(dormant(s) and still(r,s) and sr['action']=='NEXT_ROUND' and sr['accepted'] and sr['error'] is None
            and sr['mode']=='COMPOSE' and sr['presentationOrdinal']=='0'
            and sr['sessionGeneration']==r['controller']['sessionGeneration']
            and sr['expectedRevision']==r['controller']['sessionRevision']
            and int(sr['serial'])==int(r['controller']['lastViewerReceipt']['serial'])+1
            and int(sr['revision'])>int(sr['expectedRevision'])
            and s['controller']['round']==r['controller']['round']+1
            and s['port']['native']['intentEvents']==r['port']['native']['intentEvents'],
            'Actual Standard NEXT_ROUND accepted while engine work remains dormant: ' + mode)
    dialogs=checkpoint(mode,'Actual production Leave confirmation latest sanitized observation')
    require(len(dialogs)==3 and all(dormant(row['value']) and row['value']['controller']['leaveConfirmation'] for row in dialogs),
            'All three actual Leave dialogs follow native closure: ' + mode)
    cancelled=capture_observations(mode,'Leave cancelled on same concealed session')[0]
    left=capture_observations(mode,'confirmed Leave ended the session')[0]
    reused=capture_observations(mode,'new practice reuses engine and receives fresh input')[0]
    cleanup=capture_observations(mode,'production smoke cleanup complete')[0]
    require(dormant(cancelled['value']) and not cancelled['value']['controller']['leaveConfirmation']
            and cancelled['value']['controller']['sessionGeneration']==baseline_c['sessionGeneration']
            and still(dialogs[0]['value'],cancelled['value']), 'Leave cancel retains session and stable dormant native counters: ' + mode)
    for dialog,home in ((dialogs[1],left),(dialogs[2],cleanup)):
        value=home['value']; c=value['controller']
        require(dormant(value) and not c['sessionPresent'] and not c['practice'] and c['screen']=='HOME' and not c['leaveConfirmation']
                and int(c['sessionGeneration'])>int(dialog['value']['controller']['sessionGeneration'])
                and int(value['observationSequence'])>=int(dialog['value']['observationSequence'])+2
                and still(dialog['value'],value), 'Confirmed Leave returns Home with fresh observations and no dormant work growth: ' + mode)
    require(int(selections[1]['value']['controller']['sessionGeneration'])>int(left['value']['controller']['sessionGeneration'])
            and selections[1]['value']['controller']['sessionGeneration']==reused['value']['controller']['sessionGeneration']
            and int(selections[1]['value']['port']['native']['inputGeneration'])>int(left['value']['port']['native']['inputGeneration'])
            and live(reused['value']) and concealed(reused['value']), 'New practice has new session/input generation and real fresh selection/Hide on retained engine: ' + mode)
    behaviors.append(dict(mode=mode,firstEntry=refs([initial])[0],standardHandCheckpoints=refs(standard),
        realSelectionOccurrencesChronological=refs(selections),hideOccurrencesChronological=refs(hides),
        measuredPlay=refs(before_play)[0],acceptedNativePlay=refs([accepted])[0],actualNativeReceipt=receipt,
        standardReturn=refs([returned])[0],acceptedStandardAction=refs([standard_action])[0],actualStandardReceipt=sr,
        leaveDialogsChronological=refs(dialogs),leaveCancelled=refs([cancelled])[0],confirmedLeave=refs([left])[0],
        newPractice=refs([reused])[0],finalCleanup=refs([cleanup])[0],allReferencedInvariantsPassed=True))
    for capture in ordered([row for row in captures if row['caseMode']==mode]):
        paired=checkpoint(mode,capture['sourceAttachmentName']+' latest sanitized observation')
        candidates=[row for row in paired if 0 <= row['exportMetadata']['timestamp']-capture['exportMetadata']['timestamp'] <= 0.05]
        require(len(candidates)==1,'Source-named screenshot has one exact-case chronological paired observation')
        pair=candidates[0]
        capture_pairs.append(dict(capture=refs([capture])[0],observation=refs([pair])[0],
                                  deltaSeconds=pair['exportMetadata']['timestamp']-capture['exportMetadata']['timestamp']))

coverage_row=scrolls[0]; coverage=coverage_row['value']
before=checkpoint('3d','3d round '+str(coverage['round'])+' selected hand before body scroll')[0]
after=capture_observations('3d','round '+str(coverage['round'])+' full native action bounds preserve selection')[0]
b,a=before['value'],after['value']
require(coverage['beforeObservationSequence']==b['observationSequence'] and coverage['afterObservationSequence']==a['observationSequence']
        and coverage['beforeRendererSequence']==b['port']['renderer']['sequence'] and coverage['afterRendererSequence']==a['port']['renderer']['sequence'],
        'Original body-scroll report joins exact original before/after observation and renderer sequences')
require(live(b) and live(a) and selected(b) and selected(a), 'Body scroll before/after remains interactive with selected first card')
controller_keys=('sessionGeneration','presentationOrdinal','privacyEpoch','sessionRevision','projectedRendererRevision','projectedSessionRevision',
                 'phase','round','handCount','ownTurn','canSendAction','pending','canPlay','canChallenge','lastViewerReceipt')
native_keys=('presentationGeneration','lifecycleGeneration','inputGeneration','intentEvents','exitEvents','rejectedEvents')
renderer_keys=('presentationMode','revision','viewport','handConcealed','selectedCount','privateFaceCount','privateLabelCount')
require(all(a['controller'][key]==b['controller'][key] for key in controller_keys)
        and all(a['port']['native'][key]==b['port']['native'][key] for key in native_keys)
        and all(a['port']['renderer'][key]==b['port']['renderer'][key] for key in renderer_keys)
        and a['port']['geometry']==b['port']['geometry'] and a['port']['native']['queuedEvents']==b['port']['native']['queuedEvents']==0,
        'Body scroll preserves complete source input/privacy/presentation/revision/authority context')
require(coverage['authorityIntentCountBefore']==b['port']['native']['intentEvents']==a['port']['native']['intentEvents']==coverage['authorityIntentCountAfter']
        and coverage['scrollGestures']>0 and coverage['canChallenge'] is True and coverage['challengeCoverage']=='full_bounds_after_native_scroll',
        'Actual body scroll exercised available Challenge without authority action')

def inside(outer,inner):
    return inner[0]>=outer[0]-0.5 and inner[1]>=outer[1]-0.5 and inner[0]+inner[2]<=outer[0]+outer[2]+0.5 and inner[1]+inner[3]<=outer[1]+outer[3]+0.5

renderer=a['port']['renderer']; viewport=[0,0,renderer['viewport']['width'],renderer['viewport']['height']]
require({item['action'] for item in coverage['controls']}=={'lobby','play','challenge'},'Actual scroll coverage has all three required actions')
for control in coverage['controls']:
    candidates=[item for item in renderer['controls'] if item['group']=='partydeck_action_'+control['action'] and item['cardIndex']==-1]
    require(len(candidates)==1,'Post-scroll action uniquely present in original renderer controls')
    actual=candidates[0]
    require(actual['visible'] and actual['enabled'] is True and all(control[key]==actual[key] for key in ('rect','clipRect','enabled'))
            and actual['rect'][2]>=48 and actual['rect'][3]>=48
            and inside(viewport,actual['clipRect']) and inside(actual['clipRect'],actual['rect']),
            'Original post-scroll action has complete at-least-48-point bounds within actual clip and viewport: '+control['action'])

body_review=dict(original=coverage_row['original'],coverage=coverage,before=refs([before])[0],after=refs([after])[0],
                 fullBoundsAndAllSourceInputPrivacyInvariantsIndependentlyChecked=True,
                 actualActions=['lobby','play','challenge'],nativeChallengeExecuted=False)
report=dict(runId=IDENTITY[0],headSha=HEAD,attempt=1,reviewer='ios_review',reviewedAtUtc=datetime.now(timezone.utc).isoformat(),
    disposition='passed for exact current Debug Simulator named outcomes and source-scoped production behavior',
    reviewerScript=record(Path(__file__)),ownerAudits=owner_records,ownerExecutions=execution_records,
    priorIndependentNativeJobLogReview=prior_record,originalInventory=inventory_record,originalIntegrity=integrity_record,
    independentlyHashedRetainedOriginalMemberCount=len(originals),originalRecords=list(originals.values()),
    dedicatedLogReviews=logs,originalSummaryReviews=summaries,effectiveQualificationSettings=settings,
    javaSwiftExchange=dict(original=original('build/ci/ios/interop/result.json'),orchestration=original('build/ci/ios/interop/orchestration.json'),passed=True),
    originalManifests=manifest_records,sourceScopedSchema=schema_record,
    observedAttachments=dict(ordinaryCaptures=10,uikitCaptures=0,productionCaptures=41,productionObservations=64,productionBodyScroll=1,opaqueJsonDecoded=0),
    everyOwnerPointerAndOriginalHashReconciled=True,chronologyBasis='Original attachment timestamps, exact case/source label, observation sequence, session and presentation generations; manifest ordinals remain original reverse order.',
    productionBehaviorReviews=behaviors,sourceNamedCaptureObservationPairs=capture_pairs,bodyScrollReview=body_review,
    checksPassed=len(CHECKS),mediaDirectlyViewedByThisScript=False,
    scopeLimitations=[
        'Direct original image viewing is recorded separately by the human-facing reviewer; this script does not infer pixels from observation counters or geometry.',
        'Approval covers the exact executed Debug arm64 Simulator qualification cases and their retained source-scoped evidence.',
        'The ordinary UIKit gate has no original exported images; its three named native tests and settings are reviewed as test evidence.',
        'No original ZIP read or rehash, native rerun, process topology audit, duplicate selected-source audit, or package/native-binary join was performed.',
        'No shipping-picker test ran in this workflow selection; no physical-device, signing/store, physical-network, performance, or historical-fix acceptance is added.',
        'Available Challenge was checked for complete post-scroll bounds and unchanged context; no Challenge action acceptance is claimed.'
    ])
payload=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
allocated=sum(path.stat().st_blocks*512 for path in OWN.rglob('*') if path.is_file())
require(allocated+((len(payload)+4095)//4096)*4096<=1048576,'Reviewer artifact allocation stays within 1 MiB')
output=OWN/'dedicated-native-results-independent-review-v1.json'
with output.open('xb') as stream: stream.write(payload)
print(json.dumps(dict(receipt=record(output),observedCases={key:len(value['finished']) for key,value in logs.items()},
                      attachments=report['observedAttachments'],bodyScroll=coverage,checksPassed=report['checksPassed']),indent=2))
