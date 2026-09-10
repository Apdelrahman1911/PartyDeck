#!/usr/bin/env python3
"""Audit existing desktop validation originals; never run Godot or view images."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parent
OWNER = Path('/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    frozen_raw = (OWNER/'freeze.json').read_bytes()
    assert sha(frozen_raw) == '7c274914ff2f3d8e500458ef5303492e02d2af2144c04e2d16f3659bf8a8b5e3'
    frozen = {r['path']:r for r in json.loads(frozen_raw)['files']}
    originals = {}

    def read(relative, retain=True):
        path = OWNER/relative
        raw = path.read_bytes()
        expected = frozen[relative]
        assert sha(raw) == expected['sha256'] and len(raw) == expected['bytes'], relative
        record = dict(original=str(path), bytes=len(raw), sha256=sha(raw))
        if retain:
            target = ROOT/'validation-originals'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                assert target.read_bytes() == raw
            else:
                target.write_bytes(raw)
            record['retained'] = str(target.relative_to(ROOT))
        originals[relative] = record
        return raw

    summary_raw = read('receipts/validation-summary.json')
    assert sha(summary_raw) == 'abcd5171d3536396a051c9748223f9b045625f76a2e16f413d469b50f0dee76f'
    summary = json.loads(summary_raw)
    version = json.loads(read('receipts/godot-version.json'))
    assert version['stdout'].strip() == '4.7.2.stable.official.ed1daf0bf' and version['returncode'] == 0
    source = json.loads((ROOT/'candidate-source-review.json').read_text())
    source_map = {r['path']:r for r in source['files']}
    tests, count = [], 0
    for entry in summary['receipts']:
        raw = read(entry['path'])
        assert sha(raw) == entry['sha256']
        receipt = json.loads(raw)
        assert receipt['passed'] and receipt['exit_code'] == 0 and not receipt['timed_out']
        assert receipt['binary_sha256'] == version['binary_sha256'] and not receipt['engine_errors']
        parts = Path(entry['path']).parts
        project, case = parts[1], parts[2]
        assert project in ['baseline','candidate']
        key = 'candidateSHA256' if project == 'candidate' else 'originalAndBaselineAndDiagnosticSHA256'
        for path,digest in receipt['source_hashes'].items():
            assert source_map[path][key] == digest
        command = receipt['command']
        assert command[command.index('--path')+1] == str(OWNER/project)
        log_parts = [read(str(Path(entry['path']).parent/name)).decode() for name in ['engine.log','stdout.log','stderr.log']]
        combined = '\n'.join(log_parts)
        assert not re.search(r'(?:^|\n)\s*(?:SCRIPT ERROR:|ERROR:|Parse Error:)',combined)
        item = dict(project=project,case=case,receiptSHA256=sha(raw),exitCode=0,scriptErrors=False)
        if case != 'import':
            assert '--headless' not in command and 'xvfb-run' in command
            assert command[command.index('--rendering-method')+1] == 'gl_compatibility'
            assert command[command.index('--rendering-driver')+1] == 'opengl3'
            assert receipt['environment_overrides']['LIBGL_ALWAYS_SOFTWARE'] == '1'
            assert 'Compatibility - Using Device: Mesa - llvmpipe' in combined
            script = command[command.index('--script')+1]
            script_path = str(Path(project)/script.removeprefix('res://')) if script.startswith('res://') else str(Path(script).relative_to(OWNER))
            script_raw = read(script_path)
            item['executedScript'] = dict(path=script_path,sha256=sha(script_raw))
            report_path = str(Path(entry['path']).parent/'report.json')
            report_raw = read(report_path)
            assert sha(report_raw) == receipt['report_sha256']
            report = json.loads(report_raw)
            assert report['result'] == receipt['reported_result'] == 'passed'
            checks = report.get('checks',[])
            assert all(check['passed'] is True for check in checks)
            assert len(checks) == receipt['checks'] == entry['checks']
            count += len(checks)
            item['originalReport'] = dict(path=report_path,sha256=sha(report_raw),numberedChecks=len(checks),allChecksPassed=True)
            item['renderer'] = 'Actual desktop OpenGL Compatibility, Mesa llvmpipe, Xvfb; not native iOS.'
        tests.append(item)
    assert count == summary['numbered_checks'] == 560
    assert len(tests) == 13
    pixels_raw = read('evidence/pixel-comparison.json')
    assert sha(pixels_raw) == summary['pixel_comparison_sha256'] == '52949f7e68018aff80760409f95958825a91e2714fe6703dce2c3cfff37519cd'
    pixels = json.loads(pixels_raw)
    comparisons = []
    for pair in pixels['comparisons']:
        raw = {}
        for project in ['baseline','candidate']:
            name = 'evidence/'+project+'/'+pair['case']+'/'+pair['capture']
            raw[project] = read(name,retain=False)
            assert sha(raw[project]) == pair[project+'_png_sha256']
            assert raw[project][:8] == b'\x89PNG\r\n\x1a\n'
            assert list(struct.unpack('>II',raw[project][16:24])) == pair[project+'_size']
        assert raw['baseline'] == raw['candidate'] and pair['byte_identical_png']
        comparisons.append(dict(case=pair['case'],capture=pair['capture'],
                                sha256=sha(raw['candidate']),bytes=len(raw['candidate']),exactBytesEqual=True))
    assert len(comparisons) == pixels['captures_compared'] == pixels['byte_identical_captures'] == 20
    fixture_binding = json.loads(read('receipts/fixture-binding.json'))
    for file in fixture_binding['files']:
        raw = read('fixtures/'+file['path'])
        assert sha(raw) == file['sha256'] and len(raw) == file['bytes']
    post_raw = read('receipts/post-validation-source-verification.json')
    assert sha(post_raw) == summary['post_validation_source_verification_sha256']
    post = json.loads(post_raw)
    assert post['checked_files_per_project'] == 155 and all(x['baseline_matches'] and x['candidate_matches_frozen_delta'] for x in post['source_checks'])
    read('receipts/run_check.py')
    result = dict(verifiedUtc=datetime.now(timezone.utc).isoformat(),ownerRoot=str(OWNER),
        ownerFreezeSHA256=sha(frozen_raw),summarySHA256=sha(summary_raw),
        originalBindings=list(originals.values()),tests=tests,numberedChecks=count,
        allNumberedChecksPassed=True,scriptErrors=False,exactPNGComparisons=comparisons,
        sourceFixtureScope=fixture_binding['scope'],
        limits=['Existing owner-run desktop evidence audited independently; reviewer did not execute Godot.',
                'PNG bytes and dimensions were verified from files already on disk. Images were not decoded, viewed, extracted, or copied.',
                'Desktop software-renderer equivalence does not qualify iOS behavior or prove native entry latency improvement.',
                'Numbered checks exclude procedural assertions in the scene checker.',
                'Resource contract probe derives a public claim in a recipient-safe source-test projection; its card counts do not describe native run 34525504734.',
                'The original engine binary hash comes from the owner version receipt; this review did not rescan the binary.'])
    target = ROOT/'validation-original-audit.json'
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(sha256=sha(target.read_bytes()),originals=len(originals),runs=len(tests),checks=count,pngPairs=len(comparisons))))


if __name__ == '__main__':
    main()
