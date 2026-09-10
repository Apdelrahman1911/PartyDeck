"""Apply a pinned prior selected-JNI audit only to identical complete DEX bytes."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REFERENCE = ROOT.parent / 'android-jni-standard-root-validation-20260910/jni-abi-audit.json'
FREEZE = Path('/tmp/partydeck-api36-native-ready-34496282263-v1/audit-freeze-v1.json')


def identity(path):
    digest = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def dex_set(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        rows = []
        for name in sorted(n for n in names if n.endswith('.dex')):
            data = archive.read(name)
            assert data[:4] == b'dex\n' and struct.unpack_from('<I', data, 32)[0] == len(data)
            rows.append({'name': name, 'bytes': len(data), 'sha256': sha256(data).hexdigest(),
                         'classes': struct.unpack_from('<I', data, 96)[0]})
    assert rows
    return rows


assert identity(REFERENCE)['sha256'] == '4a9cc5457b1b0c923ecb47e836705432e297a6f4938ef24c49657bcfa47584cc'
assert identity(FREEZE)['sha256'] == 'ebd5383f31dd44ab1e97df987cf618b5ace726a3ee6a0944730c876169a06b98'
reference = json.loads(REFERENCE.read_text())
freeze = json.loads(FREEZE.read_text())
auditor_files = []
for row in freeze['files']:
    actual = identity(Path(row['path']))
    assert actual == row, row['path']
    auditor_files.append(actual)
assert reference['passed'] and reference['nativeExecutionPerformed'] is False
assert reference['expectedDeclarations'] == reference['presentDeclarations'] == len(reference['results'])
assert all(v['declarationPresent'] and v['passed'] and not v['missingDescriptorClasses'] for v in reference['results'])
assert identity(Path(reference['contract']['path']))['sha256'] == reference['contract']['sha256']
reference_apk = Path(reference['apk']['path'])
assert identity(reference_apk)['sha256'] == reference['apk']['sha256']
assert dex_set(reference_apk) == reference['dexFiles']
package_audit = json.loads((ROOT / 'review/package-audit.json').read_text())
assert package_audit['run_id'] == 34503251315 and package_audit['commit'] == '1cd34a36753ed0112e6684f6525592dab8ef2edb'
current = {}
for variant in ('unsigned-release', 'optimized-test-signed'):
    audited = package_audit['packages'][variant]
    path = Path(audited['artifact']['path'])
    actual = identity(path)
    assert actual == audited['artifact']
    dex = dex_set(path)
    assert dex == reference['dexFiles'], variant
    assert [{'path': row['name'], 'bytes': row['bytes'], 'sha256': row['sha256'],
             'class_definition_count': row['classes']} for row in dex] == audited['dex']
    current[variant] = {'artifact': actual, 'completeDexSet': dex, 'matchesPinnedPriorAuditDexBytes': True}
report = {
    'runId': 34503251315, 'headSha': package_audit['commit'],
    'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'result': 'Prior selected-JNI pass applies by identical complete DEX bytes.',
    'priorAudit': identity(REFERENCE), 'priorApkIndependentlyRehashed': identity(reference_apk),
    'auditorFreeze': identity(FREEZE), 'auditorFilesRehashed': auditor_files,
    'currentPackages': current, 'packageAudit': identity(ROOT / 'review/package-audit.json'),
    'selectedExpectedDeclarations': reference['expectedDeclarations'],
    'selectedPresentDeclarations': reference['presentDeclarations'],
    'allSelectedDescriptorClassesPresent': True, 'parserRerun': False,
    'nativeExecutionPerformedByReviewer': False,
    'scope': reference['scope'],
    'limits': 'This receipt applies the pinned root-owned local ABI audit to the current original CI APK DEX bytes. It does not apply the old missing-method result or establish universal Godot JNI compatibility. Current native Ready/lifecycle evidence is separately bound in runtime-result-triage.json.',
    'auditScript': identity(Path(__file__)),
}
output = ROOT / 'review/jni-applicability-audit.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'receipt': identity(output), 'currentDexSetsMatchPriorAudit': True,
                  'selectedExpectedDeclarations': report['selectedExpectedDeclarations'],
                  'selectedPresentDeclarations': report['selectedPresentDeclarations']}, indent=2))
