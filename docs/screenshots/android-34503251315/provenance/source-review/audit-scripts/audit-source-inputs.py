"""Read-only current-source fingerprint and CI/JNI configuration binding."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
SOURCE = ROOT.parent / 'source-1cd34a3/source-1cd34a3'
REVIEW = ROOT / 'review'
REFERENCE = ROOT.parent / '34485028785/review/reference/comparison-34478725424/partydeck-last-light.receipt.json'
REFERENCE_PIN = '099adc524757515d4e2449a21ee00e4c1419df712690b37bc9e4a4ec6f4d3ecb'
JNI_REVIEW = Path('/tmp/partydeck-godot-jni-independent-review-v1/review.json')
JNI_REVIEW_PIN = '490b57f6f67b232117f7fda1796164068c0b1801939c07b085840aedb91228f5'


def digest(path):
    with path.open('rb') as stream:
        value = sha256()
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


binding = json.loads((ROOT / 'shared-source-reuse.json').read_text())
assert binding['runId'] == 34503251315 and binding['headSha'] == '1cd34a36753ed0112e6684f6525592dab8ef2edb'
assert binding['sharedSourceDirectory'] == str(SOURCE)
assert digest(REFERENCE) == REFERENCE_PIN and digest(JNI_REVIEW) == JNI_REVIEW_PIN
reference = json.loads(REFERENCE.read_text())
jni_review = json.loads(JNI_REVIEW.read_text())
project = SOURCE / 'godot/renderer'
excluded_dirs = {'.git', '.godot', '.gradle', '.idea', '__pycache__', 'build', 'tests', 'checks', 'fixtures'}
excluded_names = {'.gitignore', '.DS_Store', 'README.md', 'export_credentials.cfg', '.env'}
private_suffixes = {'.jks', '.keystore', '.p12', '.pfx', '.key', '.pem', '.mobileprovision'}


def excluded(rel):
    return (bool(set(rel.parts) & excluded_dirs) or rel.as_posix().startswith(('assets/proofs/', 'assets/sources/'))
            or rel.name in excluded_names or rel.name.startswith('.env.') or rel.suffix.lower() in private_suffixes
            or (rel.suffix.lower() == '.md' and 'licenses' not in rel.parts))


files, omitted = [], []
for directory, directories, names in os.walk(project, followlinks=False):
    parent = Path(directory)
    for name in list(directories):
        path, rel = parent / name, (parent / name).relative_to(project)
        if excluded(rel) or (path / '.gdignore').exists():
            directories.remove(name)
            omitted.append(rel.as_posix() + '/')
        else:
            assert not path.is_symlink()
    for name in names:
        path, rel = parent / name, (parent / name).relative_to(project)
        if excluded(rel):
            omitted.append(rel.as_posix())
            continue
        assert path.is_file() and not path.is_symlink()
        files.append({'path': rel.as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)})
files.sort(key=lambda item: item['path'])
tools = [{'path': name, 'sha256': digest(SOURCE / 'godot/tools' / name)}
         for name in ['renderer.py', 'partydeck_pck.py', 'scene_check.gd', 'godot-pins.json']]
fingerprint = sha256(json.dumps({'files': files, 'tools': tools}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
assert files == reference['inputs']['files'] and tools == reference['inputs']['tools']
assert sorted(omitted) == reference['inputs']['excluded']
assert fingerprint == reference['inputs']['fingerprint']

wrapper = SOURCE / 'scripts/smoke-android-emulator.sh'
workflow = SOURCE / '.github/workflows/validate.yml'
rules = SOURCE / 'godot/android-renderer/consumer-rules.pro'
assert digest(wrapper) == '1746e4fabbf78457c0328bdffa6b50da5c78d765562dc1eb0771c6c8c7d623f0'
assert digest(rules) == jni_review['approvedRules']['sha256']
assert rules.stat().st_size == jni_review['approvedRules']['bytes']
text = wrapper.read_text()
assert 'local engine_arguments=() runtime_timeout=20m' in text
assert 'if [[ "$PARTYDECK_ANDROID_API" == 36 ]]; then\n    # The qualified API36 path' in text
assert 'engine_arguments=(--engine-gameplay --engine-package-inputs "$output/package-inputs.json")' in text
assert 'timeout --signal=TERM --kill-after=15s "$runtime_timeout"' in text
workflow_text = workflow.read_text()
assert 'timeout-minutes: ${{ inputs.android_godot_session && 55 || 30 }}' in workflow_text
assert '            !docs/screenshots/**\n            !artifacts/**' in workflow_text

summary = {
    'audit_result': 'pass', 'run_id': 34503251315, 'source_revision': binding['headSha'],
    'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'shared_source_binding': identity(ROOT / 'shared-source-reuse.json'),
    'accepted_pack_receipt': identity(REFERENCE), 'source_inputs': files,
    'source_tools': tools, 'excluded': sorted(omitted), 'source_fingerprint': fingerprint,
    'source_inputs_count': len(files), 'source_matches_accepted_comparison_inputs': True,
    'expected_pack_sha256': reference['pack']['sha256'], 'expected_pack_bytes': reference['pack']['bytes'],
    'expected_pack_entries': len(reference['pack']['entries']),
    'checker': identity(SOURCE / 'scripts/smoke-android-godot-session.py'),
    'helper': identity(SOURCE / 'scripts/smoke-android-ui.py'),
    'source_configuration': {
        'wrapper': identity(wrapper), 'workflow': identity(workflow),
        'wrapper_matches_reviewed_budget_fix': True,
        'native_cumulative_per_variant_minutes': 20,
        'native_termination_signal': 'TERM', 'native_kill_grace_seconds': 15,
        'workflow_runtime_step_minutes_for_requested_native_run': 55,
        'engine_gameplay_arguments_api': [36],
        'api35_source_invokes_engine_gameplay': False,
        'report_upload_excludes_docs_screenshots_and_root_artifacts': True,
        'jni_rules': identity(rules), 'jni_independent_source_review': identity(JNI_REVIEW),
        'jni_rules_exactly_match_independently_approved_rules': True,
    },
    'scope': 'Current exact source was independently fingerprinted against accepted renderer-pack inputs. CI wrapper and reviewed JNI rule bytes were checked without executing source. This is configuration/provenance evidence; current package bytes, actual invocation and runtime outcomes still require this run\'s original artifacts.',
    'audit_script': identity(Path(__file__)),
}
REVIEW.mkdir(exist_ok=True)
out = REVIEW / 'source-inputs-audit.json'
with out.open('x') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps({'receipt': identity(out), 'source_fingerprint': fingerprint,
                  'source_inputs': len(files), 'source_tools': len(tools),
                  'expected_pack_sha256': reference['pack']['sha256'],
                  'approved_jni_rules_match': True, 'native_per_variant_minutes': 20,
                  'api35_source_invokes_engine_gameplay': False}, indent=2))
