"""Audit retained Godot comparison artifacts without executing builds or devices."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

run, head = sys.argv[1:3]
base = Path('/tmp/partydeck-engine-ci') / run
build = base / 'godot-comparison-builds/godot/qualification/build'
source = base / ('source-' + head[:7])
sys.path.insert(0, str(source / 'godot/android-checks'))
from evidence import read_png
read = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def png_record(path):
    picture = read_png(path.read_bytes())
    width, height = picture.width, picture.height
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
            'width': width, 'height': height, 'pngVerifiedAndDecoded': True}

status = read(base / 'last-run-status.json')
assert status['head_sha'] == head
pack = build / 'renderer/partydeck-last-light.pck'
pack_sha = digest(pack)
assert digest(base / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.pck') == pack_sha
assert read(pack.with_suffix('.receipt.json'))['pack']['sha256'] == pack_sha
assert 'PCK checks passed:' in (base / 'source-pack-check.log').read_text()
summary = {'runId': int(run), 'headSha': head, 'conclusion': status['conclusion'],
           'scope': 'Read-only retained artifact audit; no Gradle, engine, device execution or dispatch.',
           'sourcePackCheckPassed': True, 'packSha256': pack_sha, 'packBytes': pack.stat().st_size}
packages = []
for path in [base / 'godot-comparison-runtime-apk/modules/androidHost/outputs/apk/debug/androidHost-debug.apk',
             build / 'modules/androidHost/outputs/apk/release/androidHost-release-unsigned.apk',
             build / 'modules/androidHost/outputs/bundle/release/androidHost-release.aab']:
    with zipfile.ZipFile(path) as archive:
        prefix = 'base/' if path.suffix == '.aab' else ''
        entry = prefix + 'assets/partydeck-last-light.pck'
        with archive.open(entry) as stream:
            embedded = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert embedded == pack_sha
        inventory = defaultdict(lambda: {'files': 0, 'uncompressedBytes': 0, 'zipCompressedBytes': 0})
        for item in archive.infolist():
            if item.filename.startswith(prefix + 'lib/') and item.filename.endswith('.so'):
                abi = item.filename.removeprefix(prefix).split('/')[1]
                inventory[abi]['files'] += 1
                inventory[abi]['uncompressedBytes'] += item.file_size
                inventory[abi]['zipCompressedBytes'] += item.compress_size
    packages.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path),
                     'embeddedPackSha256': embedded, 'nativeLibraryInventoryByAbi': dict(inventory)})
summary['packages'] = packages
summary['packageSizeScope'] = 'Archive/ZIP entry sizes only; no installed or per-device split size claim.'
suites = []
for path in sorted(build.rglob('TEST-*.xml')):
    if 'test-results' not in path.parts:
        continue
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    counts = {key: int(root.get(key, 0)) for key in ['tests', 'failures', 'errors', 'skipped']}
    assert counts['tests'] == len(cases)
    assert not any(case.find(tag) is not None for case in cases for tag in ['failure', 'error', 'skipped'])
    assert counts['failures'] == counts['errors'] == counts['skipped'] == 0
    suites.append({'name': root.get('name'), **counts, 'actualCases': len(cases), 'path': str(path)})
summary['junitSuites'] = suites
summary['junitTotals'] = {key: sum(s[key] for s in suites) for key in ['tests', 'failures', 'errors', 'skipped', 'actualCases']}
checker_log = (build / 'ci/android-checker-tests.log').read_text()
summary['checkerHostTests'] = int(re.findall(r'Ran (\d+) tests', checker_log)[-1])
assert re.search(r'^OK$', checker_log, re.M)
boundary = read(build / 'ci/native-boundary/results/report.json')
assert boundary['result'] == 'passed' and all(c['passed'] is True for c in boundary['checks'])
boundary_log = (build / 'ci/native-boundary/runtime.log').read_text()
assert not re.search(r'(?m)^(?:SCRIPT ERROR:|ERROR:)|Parse Error:', boundary_log)
summary['packedNativeBoundary'] = {'passed': True, 'checks': len(boundary['checks']), 'scope': boundary['limitations']}
desktop = read(build / 'ci/desktop/report.json')
assert desktop['sourceCommit'] == head and desktop['workingTreeDirty'] is False
assert desktop['rendererArtifact']['sha256'] == pack_sha and desktop['status'] == 'passed'
results = desktop['results']
assert len(results) == 2 and results[0]['authorityTrace'] == results[1]['authorityTrace']
assert results[0]['authorityTraceSha256'] == results[1]['authorityTraceSha256']
desktop_captures = []
for path in sorted((build / 'ci/desktop').rglob('*.receipt.json')):
    value = read(path)
    png = path.with_suffix('').with_suffix('.png')
    item = png_record(png)
    assert item['sha256'] == value['sha256'] and [item['width'], item['height']] == [value['width'], value['height']]
    assert value['sourceCommit'] == head and value['workingTreeDirty'] is False
    assert value['rendererArtifact']['sha256'] == pack_sha
    assert value['sourceFingerprintSha256'] == desktop['sourceFingerprintSha256']
    desktop_captures.append(item)
summary['desktop'] = {'passed': True, 'sameAuthorityTrace': True,
                      'traceViews': len(results[0]['authorityTrace']),
                      'traceSha256': results[0]['authorityTraceSha256'],
                      'capturesVerified': len(desktop_captures), 'captures': desktop_captures}

summary['scope'] = 'Completed producer-job artifact audit; native case qualification is recorded separately.'
summary['producerAuditPassed'] = True
output = base / 'producer-evidence-summary.json'
output.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'output':str(output),'junitTotals':summary['junitTotals'],'checkerHostTests':summary['checkerHostTests'],'boundaryChecks':summary['packedNativeBoundary']['checks'],'desktop':{k:summary['desktop'][k] for k in ['passed','sameAuthorityTrace','traceViews','capturesVerified']},'packages':[{k:r[k] for k in ['path','bytes','sha256']} for r in packages]},indent=2))
