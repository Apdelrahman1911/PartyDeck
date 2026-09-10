#!/usr/bin/env python3
"""Read frozen 2D proposal evidence and write a separate independent audit."""
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/tmp/partydeck-2d-initial-layout-34488350932-v1')
OUT = Path('/tmp/partydeck-2d-initial-layout-independent-validation-v1.json')
checks, failures = [], []


def check(condition, label):
    (checks if condition else failures).append(label)


def read_json(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def contains(rect, clip):
    return rect[0] >= clip[0] and rect[1] >= clip[1] and rect[0] + rect[2] <= clip[0] + clip[2] and rect[1] + rect[3] <= clip[1] + clip[3]


def reveal(measurement):
    return next(c for c in measurement['diagnostics']['controls'] if c['group'] == 'partydeck_action_reveal')


freeze_path = ROOT / 'freeze.json'
freeze = read_json(freeze_path)
check(sha(freeze_path) == 'b0f40415c147183039474ff135e7d55f45a9ac089728097a69702465bfff7d85', 'Frozen proposal identity matches the assigned review.')
for item in freeze['artifacts']:
    p = Path(item['path'])
    check(p.stat().st_size == item['bytes'] and sha(p) == item['sha256'], 'Frozen artifact exact bytes: ' + str(p.relative_to(ROOT)))

trees = {}
for tree in ['baseline', 'candidate']:
    prefix = str(ROOT / tree) + '/'
    trees[tree] = {item['path'][len(prefix):]: item['sha256'] for item in freeze['artifacts'] if item['path'].startswith(prefix)}
check(trees['baseline'].keys() == trees['candidate'].keys(), 'Archived baseline and candidate source trees have the same frozen file set.')
source_differences = [p for p in trees['baseline'] if trees['baseline'][p] != trees['candidate'].get(p)]
check(source_differences == ['presentations/two_d/table.gd'], 'Only table.gd differs between the frozen source trees.')
baseline_source = ROOT / 'baseline/presentations/two_d/table.gd'
candidate_source = ROOT / 'candidate/presentations/two_d/table.gd'
expected_patch = ''.join(difflib.unified_diff(baseline_source.read_text().splitlines(keepends=True), candidate_source.read_text().splitlines(keepends=True), fromfile='a/godot/renderer/presentations/two_d/table.gd', tofile='b/godot/renderer/presentations/two_d/table.gd'))
check(expected_patch == (ROOT / 'two-d-initial-reveal.patch').read_text(), 'Frozen patch exactly reproduces the baseline-to-candidate source diff.')

paths = [ROOT / 'results' / n for n in ['baseline-layout.json', 'candidate-v2-layout.json', 'candidate-v2-wrap-layout.json']]
baseline, candidate, wrapping = [read_json(p) for p in paths]
check(len(baseline['cases']) == 13 and len(candidate['cases']) == 13 and len(wrapping['cases']) == 9, 'Recorded case counts are 13 baseline, 13 candidate comparisons, and 9 candidate wrapping cases.')
baseline_cases = {c['case']['name']: c for c in baseline['cases']}
case_rows = []
for dataset, dataset_name in [(baseline, 'baseline'), (candidate, 'candidate'), (wrapping, 'candidate-wrapping')]:
    for case in dataset['cases']:
        name = case['case']['name']
        settled = [f for f in case['frames'] if f['frame'] >= 2]
        check([f['frame'] for f in settled] == [2, 4, 8, 12], dataset_name + '/' + name + ': recorded frames 2, 4, 8, 12 present.')
        final = settled[-1]['measurement']
        stable_keys = ['rect', 'scrollMax', 'scrollPage', 'scrollVertical']
        check(all(f['measurement']['diagnostics']['controls'] == final['diagnostics']['controls'] and all(f['measurement']['components']['_body_scroll'][k] == final['components']['_body_scroll'][k] for k in stable_keys) for f in settled), dataset_name + '/' + name + ': control/scroll geometry stable across the recorded settled frames.')
        check(all(f['measurement']['diagnostics']['handConcealed'] and all(f['measurement']['diagnostics'][k] == 0 for k in ['privateFaceCount', 'privateLabelCount', 'selectedCount']) for f in settled), dataset_name + '/' + name + ': concealed initial state has no private faces, labels, or selection.')
        if dataset_name == 'baseline':
            continue
        r = reveal(final)
        props = case['case']
        compact = props['width'] < 860 and 500 <= props['height'] < 800 and props['textScale'] < 1.5
        normal = props['textScale'] == 1
        check(final['components']['_body_scroll']['scrollVertical'] == 0, name + ': initial scroll is zero.')
        if normal:
            check(contains(r['rect'], r['clipRect']) and r['rect'][3] >= 56 and r['enabled'] and r['visible'], name + ': whole normal-text initial Reveal is enabled, visible, and at least 56 units high.')
        public = {k: {j: final['components'][k][j] for j in ['rect', 'text', 'visible']} for k in ['_turn', '_rank', '_claim']}
        if compact:
            check(all(public[k]['visible'] and contains(public[k]['rect'], [0, 0, props['width'], props['height']] if k == '_turn' else r['clipRect']) for k in public), name + ': compact initial turn, rank, and claim rectangles are fully contained.')
            check(not final['components']['_surface']['visible'] and not final['components']['_cover_art']['visible'] and not final['components']['_hand_title']['visible'] and not final['components']['_cover_description']['visible'], name + ': compact decorative content is hidden.')
        unchanged = None
        baseline_rect = None
        if name in baseline_cases:
            original = baseline_cases[name]['frames'][-1]['measurement']
            baseline_rect = reveal(original)['rect']
            if not compact:
                unchanged = final['diagnostics']['controls'] == original['diagnostics']['controls'] and all(final['components']['_body_scroll'][k] == original['components']['_body_scroll'][k] for k in stable_keys)
                check(unchanged, name + ': comparison control/scroll geometry remains unchanged.')
        if dataset_name == 'candidate-wrapping':
            check(len(props['playerName']) == 24, name + ': duplicate-name fixture is 24 characters.')
            if props['opponentTurn']:
                check(props['playerName'] + ' · seat 2' in public['_turn']['text'], name + ': opponent turn retains duplicate-name seat disambiguation.')
            if props['latestClaim']:
                check(props['playerName'] + ' · seat 2 claimed 3 Crowns.' == public['_claim']['text'], name + ': latest claim retains actor, seat, count, and rank.')
        case_rows.append({'case': name, 'dataset': dataset_name, 'compact': compact, 'baselineReveal': baseline_rect, 'candidateReveal': r['rect'], 'clipRect': r['clipRect'], 'initialScroll': 0, 'fullyContained': contains(r['rect'], r['clipRect']), 'bottomClearance': r['clipRect'][1] + r['clipRect'][3] - r['rect'][1] - r['rect'][3], 'comparisonUnchanged': unchanged, 'publicContext': public})

input_rows = []
for report_path in sorted((ROOT / 'results').glob('source-input-*/report.json')):
    report = read_json(report_path)
    execution_path = report_path.with_name('execution.json')
    execution = read_json(execution_path)
    check(report['result'] == 'passed' and execution['exitCode'] == 0, report_path.parent.name + ': source fixture execution reports success.')
    for item in execution['inputs'] + execution['outputs']:
        p = Path(item['path'])
        check(sha(p) == item['sha256'], report_path.parent.name + ': declared execution hash matches ' + p.name)
    captures = [o for o in report['observations'] if 'capture' in o]
    check(len(captures) == 4, report_path.parent.name + ': four capture/diagnostic observations are present.')
    for i, obs in enumerate(captures):
        d = obs['diagnostics']
        check(d == read_json(Path(obs['capture']).with_suffix('.json')), report_path.parent.name + ': capture diagnostics match report ' + str(i + 1))
        private_expected = i == 1
        check(d['handConcealed'] != private_expected and d['privateFaceCount'] == (5 if private_expected else 0) and d['privateLabelCount'] == (5 if private_expected else 0) and d['selectedCount'] == (2 if private_expected else 0), report_path.parent.name + ': recorded capture privacy/selection state ' + str(i + 1))
    page = next(o for o in report['observations'] if o.get('input') == 'emulated-touch-page-drag')
    hand = next(o for o in report['observations'] if o.get('input') == 'emulated-touch-hand-drag')
    tap = next(o for o in report['observations'] if o.get('input') == 'emulated-touch-small-tap')
    check(page['after'] > page['before'] and not page['handVisible'] and page['eventCount'] == 1, report_path.parent.name + ': source page drag scrolls without revealing.')
    check(hand['after'] > hand['before'] and hand['selectedCount'] == 0, report_path.parent.name + ': source hand drag scrolls without selection.')
    check(tap['before'] == tap['after'] and tap['selectedCount'] == 1, report_path.parent.name + ': small-motion source tap selects without scrolling.')
    input_rows.append({'report': identity(report_path), 'execution': identity(execution_path), 'pageDrag': page, 'handDrag': hand, 'smallTap': tap, 'originalPngs': [o['capture'] for o in captures], 'limits': 'Mouse/touch-emulated Linux OpenGL input. Helpers call ensure_control_visible before interaction; no native acceptance or human discoverability finding.'})

source_root = Path('/root/projects/PartyDeck/godot/ios-host/build/upstream/scene/gui')
pinned = [('scroll_container.cpp', 'ed4e16ea3022b44503b09b854a9ddff57c8db384fde4748ddbc3ff708f8a5c1d', [[43, 97], [365, 441]]), ('box_container.cpp', '46b3ac01582618ceb65c248b474187f857f0af22bbc1f745a234f5785b55cea6', [[45, 160], [291, 328]]), ('panel_container.cpp', '8aaf9b7c1483bcbc233cfd1a6b4924ab8de43d309933eda51042e0a484ead56f', [[35, 51]])]
sources = []
for name, expected, ranges in pinned:
    p = source_root / name
    check(sha(p) == expected, 'Pinned upstream container source exact bytes: ' + name)
    sources.append({**identity(p), 'upstreamCommit': 'ed1daf0bf001b61586d9930840f2f1394092c079', 'readLineRanges': ranges})

result = {'schemaVersion': 1, 'issuedUtc': datetime.now(timezone.utc).isoformat(), 'reviewer': '/root/review_design', 'result': 'passed' if not failures else 'failed', 'scope': 'Read-only audit of frozen source and recorded evidence. No Godot execution, build, native run, or rewrite of source evidence.', 'sourceFreeze': identity(freeze_path), 'frozenArtifactsVerified': len(freeze['artifacts']), 'sourceTreeDifferences': source_differences, 'checksPassed': len(checks), 'checks': checks, 'failures': failures, 'geometryInputs': [identity(p) for p in paths], 'geometryCases': case_rows, 'inputReports': input_rows, 'authoritativeSources': sources, 'limits': ['Landscape/tablet conclusions are comparison geometry and unchanged source branches; no new landscape/tablet candidate PNGs were produced.', 'The 320x568 200% initial Reveal remains 93 units below full containment; helper scrolling precedes source input.', 'Nine wrapping cases cover the recorded Latin duplicate-name fixture only; they do not establish every locale, glyph, viewport, or accessibility condition.', 'PNG and diagnostic capture files are associated outputs; no native original PNG is uniquely paired to a same-frame measurement by this review.']}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'result': result['result'], 'frozenArtifactsVerified': result['frozenArtifactsVerified'], 'checksPassed': len(checks), 'failures': failures, 'geometryCases': len(case_rows), 'inputReports': len(input_rows), 'output': identity(OUT)}, indent=2))
raise SystemExit(1 if failures else 0)
