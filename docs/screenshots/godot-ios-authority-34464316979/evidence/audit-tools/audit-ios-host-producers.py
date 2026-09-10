"""Audit retained failure and producer inputs without native or Gradle execution."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

RUN, HEAD, EXPECTED_PACK = sys.argv[1:4]
BASE = Path('/tmp/partydeck-engine-ci') / RUN
SOURCE = BASE / ('source-' + HEAD[:7])
HOST = SOURCE / 'godot/ios-host'
ENGINE = BASE / 'godot-ios-host-engine'
FRAMEWORK = BASE / 'godot-ios-host-framework'
RENDERER = BASE / 'godot-ios-host-renderer'
checks = []

def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def file_receipt(path):
    return {'sha256': digest(path), 'bytes': path.stat().st_size}


def record(path):
    return {'path': str(path), **file_receipt(path)}


def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label


def write_new(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


run = read(BASE / 'last-run-status.json')
check('exact workflow run, revision, dispatch and attempt', str(run['id']) == RUN and run['head_sha'] == HEAD
      and run['event'] == 'workflow_dispatch' and run['run_attempt'] == 1)
zip_receipts = []
for name in ['godot-ios-host-engine', 'godot-ios-host-framework', 'godot-ios-host-renderer', 'godot-ios-host-renderer-evidence']:
    receipt = read(BASE / (name + '.integrity.json'))
    check('original artifact ZIP integrity: ' + name, str(receipt['runId']) == RUN and receipt['headSha'] == HEAD
          and receipt['zipDigestMatchesApi'] and receipt['zipSizeMatchesApi'])
    zip_receipts.append(receipt)

engine = read(ENGINE / 'evidence/engine-artifact.json')
expected_engine = {
    'engine_commit': 'ed1daf0bf001b61586d9930840f2f1394092c079',
    'upstream_archive': 'libgodot.ios.template_debug.arm64.simulator.a',
    'stage': 'engine_compile_only', 'platform': 'ios', 'target': 'template_debug',
    'configuration': 'Debug', 'simulator': True, 'architecture': 'arm64',
    'sdk': 'iphonesimulator', 'sdk_version': '26.4', 'lto': 'none', 'xcode_version': '26.4.1',
    'path_overrides_enabled': True, 'sdl_enabled': False,
    'native_input_scope': 'touch_and_hardware_keyboard',
    'native_module_capture_phase': 'before_scons', 'engine_checkout_policy': 'fresh_isolated_checkout',
}
for key, expected in expected_engine.items():
    check('engine configuration: ' + key, engine.get(key) == expected)
check('engine revision marker', (ENGINE / 'evidence/engine-source-commit.txt').read_text().strip() == HEAD)
native_archives = [engine, *engine['auxiliary_archives']]
check('exactly two distinct native archives', {item['artifact'] for item in native_archives}
      == {'libpartydeck_godot_ios_probe.a', 'libpartydeck_godot_camera.a'} and len(native_archives) == 2)
for item in native_archives:
    check('native archive bytes: ' + item['artifact'], file_receipt(ENGINE / 'artifacts' / item['artifact'])
          == {key: item[key] for key in ('sha256', 'bytes')})
module_hashes = {path.relative_to(HOST / 'modules').as_posix(): digest(path)
                 for path in sorted((HOST / 'modules').rglob('*'))
                 if path.is_file() and (path.suffix in {'.h', '.mm', '.py'} or path.name == 'SCsub')}
check('native module source set and hashes match archived run source', module_hashes == engine['native_module_sources'])
module_digest = hashlib.sha256(json.dumps(module_hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
check('native module snapshot aggregate', module_digest == engine['module_snapshot_sha256'])
captured = read(ENGINE / 'evidence/native-module-inputs.json')
check('pre-SCons module capture receipt', captured['capture_phase'] == 'before_scons'
      and captured['native_module_sources'] == module_hashes and captured['module_snapshot_sha256'] == module_digest)
patches = []
for patch in engine['upstream_patches']:
    manifest_path = HOST / 'patches' / (patch['name'] + '.json')
    manifest = read(manifest_path)
    check('reviewed patch provenance: ' + patch['name'],
          manifest['baseCommit'] == engine['engine_commit'] and manifest['baseVersion'] == '4.7.2-stable'
          and manifest['platformGuard'] == 'IOS_ENABLED' and patch['applied'] is True
          and manifest['patchSha256'] == patch['patch_sha256'] == digest(HOST / 'patches' / manifest['patchFile'])
          and patch['manifest_sha256'] == digest(manifest_path) and patch['files'] == manifest['files'])
    patches.append(patch['name'])
check('both maintained patches represented', sorted(patches) == ['coreaudio-dormancy', 'main-loop-access'])
before = read(ENGINE / 'evidence/upstream-audit.json')
after = read(ENGINE / 'evidence/upstream-postbuild-audit.json')
reference = read(ENGINE / 'evidence/upstream-reference-audit.json')
check('upstream source and patch hashes unchanged after compilation', before['sources'] == after['sources']
      and before['upstream_patches'] == after['upstream_patches'] == engine['upstream_patches'])
check('fresh-checkout gate rejects untracked inputs before compilation', before['no_untracked_inputs_required'] is True)
check('all three upstream audits reference exact pinned commit', all(item['commit'] == engine['engine_commit']
      and item['source_audit'] == 'passed' for item in (reference, before, after)))

framework = read(FRAMEWORK / 'evidence/authority-framework-result.json')
check('framework revision marker', (FRAMEWORK / 'evidence/authority-source-commit.txt').read_text().strip() == HEAD)
check('ARM64 Simulator debug framework build/import gate', framework['target'] == 'iosSimulatorArm64'
      and framework['configuration'] == 'debugFramework'
      and all(framework[key] is True for key in ('framework_compiled', 'expected_facade_declarations_present', 'swift_module_import_typechecked')))
framework_archive = FRAMEWORK / 'artifacts' / framework['archive']['name']
check('framework archive bytes and digest', file_receipt(framework_archive)
      == {key: framework['archive'][key] for key in ('sha256', 'bytes')})
framework_members = []
with tarfile.open(framework_archive, 'r:gz') as package:
    for name, expected in framework['framework'].items():
        member = package.getmember('PartyDeckGodotBridge.framework/' + name)
        with package.extractfile(member) as stream:
            actual = {'sha256': hashlib.file_digest(stream, 'sha256').hexdigest(), 'bytes': member.size}
        check('framework member identity: ' + name, actual == expected)
        framework_members.append({'path': member.name, **actual})

pack = read(RENDERER / 'partydeck-last-light.receipt.json')
for item in pack['inputs']['files']:
    check('renderer source: ' + item['path'], file_receipt(SOURCE / 'godot/renderer' / item['path'])
          == {key: item[key] for key in ('sha256', 'bytes')})
for item in pack['inputs']['tools']:
    check('renderer tool source: ' + item['path'], digest(SOURCE / 'godot/tools' / item['path']) == item['sha256'])
check('PCK bytes and digest', file_receipt(RENDERER / 'partydeck-last-light.pck')
      == {key: pack['pack'][key] for key in ('sha256', 'bytes')})
command = [sys.executable, '-B', str(SOURCE / 'godot/tools/renderer.py'), 'check-pack', '--pack',
           str(RENDERER / 'partydeck-last-light.pck')]
validation = subprocess.run(command, capture_output=True, text=True, timeout=60)
with (BASE / 'archived-source-pack-check.log').open('x') as stream:
    stream.write(validation.stdout + validation.stderr)
check('archived-source PCK checker succeeds without engine execution', validation.returncode == 0)

check('PCK matches coordinator candidate identity', pack['pack']['sha256'] == EXPECTED_PACK)
summary = {
    'runId': int(RUN), 'headSha': HEAD, 'attempt': 1, 'auditedAtUtc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Independent exact-source producer input audit. Neither host runtime is qualified by producer build evidence.',
    'sourceArchive': read(BASE / 'source-archive.json'), 'originalZipIntegrity': zip_receipts,
    'engineArchives': [{'artifact': item['artifact'], 'sha256': item['sha256'], 'bytes': item['bytes']} for item in native_archives],
    'engineConfiguration': expected_engine, 'nativeModuleSources': module_hashes, 'moduleSnapshotSha256': module_digest,
    'upstreamAuditedSourceCount': len(before['sources']), 'patches': patches,
    'frameworkArchive': record(framework_archive), 'frameworkMembers': framework_members,
    'pack': {'sha256': pack['pack']['sha256'], 'bytes': pack['pack']['bytes'], 'entries': len(pack['pack']['entries']),
             'sourceFiles': len(pack['inputs']['files']), 'toolFiles': len(pack['inputs']['tools']),
             'sourceFingerprint': pack['inputs']['fingerprint'], 'validationCommand': command,
             'validationLog': record(BASE / 'archived-source-pack-check.log')},
    'checks': checks,
}
write_new(BASE / 'producer-input-evidence-summary.json', summary)
print(json.dumps({'passed': True, 'checks': len(checks), 'summary': record(BASE / 'producer-input-evidence-summary.json'),
                  'packSha256': pack['pack']['sha256'], 'moduleSnapshotSha256': module_digest}), flush=True)
