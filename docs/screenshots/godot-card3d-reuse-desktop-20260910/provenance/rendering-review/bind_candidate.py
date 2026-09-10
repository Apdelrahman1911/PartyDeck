#!/usr/bin/env python3
"""Bind the exact two-file candidate and compare unaffected rendering methods."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
OWNER = Path('/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq')
SOURCE = Path('/root/projects/PartyDeck/artifacts/evidence-storage/source-c65e264/source-c65e264/godot/renderer')
DIAGNOSTIC = Path('/root/projects/PartyDeck/artifacts/evidence-storage/source-fa0fabb/source-fa0fabb/godot/renderer')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def methods(text):
    matches = list(re.finditer(r'^(?:static )?func (\w+)\(', text, re.M))
    return {m.group(1): text[m.start():matches[i+1].start() if i+1 < len(matches) else len(text)].rstrip()
            for i,m in enumerate(matches)}


def main():
    pins = {'freeze.json': '7c274914ff2f3d8e500458ef5303492e02d2af2144c04e2d16f3659bf8a8b5e3',
            'candidate-source-freeze.json': '8f1aa984995a77956c651034233ea45aaeb99f1320b068c428616d3e4199338a',
            'card3d-resource-reuse.patch': 'a904d39cb259cae75085001f4733a0d7ee49cd1f2693f8c723ae914541c9b484',
            'source-binding.json': 'b2498436798a2e44ff184ec380ce22c7127576531fe822ab77452293e42f3d4a'}
    (ROOT/'owner-receipts').mkdir()
    for name, expected in pins.items():
        raw = (OWNER/name).read_bytes()
        assert sha(raw) == expected, name
        (ROOT/'owner-receipts'/name).write_bytes(raw)
    binding = json.loads((OWNER/'source-binding.json').read_text())
    frozen = json.loads((OWNER/'candidate-source-freeze.json').read_text())
    source_paths = {r['path'] for r in binding['source_files']}
    assert len(source_paths) == 155
    changes = {r['path']:r for r in frozen['changed_files']}
    assert set(changes) == {'presentations/three_d/card_3d.gd','presentations/three_d/table.gd'}
    for name in ('baseline','candidate'):
        actual = {str(p.relative_to(OWNER/name)) for p in (OWNER/name).rglob('*') if p.is_file() and '.godot' not in p.relative_to(OWNER/name).parts}
        assert actual == source_paths, name
    records, differences, patch = [], [], ''
    for record in binding['source_files']:
        path = record['path']
        original = (SOURCE/path).read_bytes()
        baseline = (OWNER/'baseline'/path).read_bytes()
        candidate = (OWNER/'candidate'/path).read_bytes()
        diagnostic = (DIAGNOSTIC/path).read_bytes()
        assert original == baseline == diagnostic and sha(original) == record['sha256'] and len(original) == record['bytes'], path
        if path in changes:
            change = changes[path]
            assert sha(baseline) == change['before_sha256'] and sha(candidate) == change['after_sha256']
            assert len(baseline) == change['before_bytes'] and len(candidate) == change['after_bytes']
            differences.append(path)
            for name,data in [('baseline',baseline),('candidate',candidate)]:
                target = ROOT/name/path
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
            patch += ''.join(difflib.unified_diff(baseline.decode().splitlines(keepends=True), candidate.decode().splitlines(keepends=True),
                             fromfile='a/godot/renderer/'+path, tofile='b/godot/renderer/'+path))
        else:
            assert candidate == baseline, path
        records.append(dict(path=path, originalAndBaselineAndDiagnosticSHA256=sha(original), candidateSHA256=sha(candidate), changed=path in changes))
    assert patch.encode() == (OWNER/'card3d-resource-reuse.patch').read_bytes()
    facts = {}
    for name in ['card_3d.gd','table.gd']:
        old = methods((OWNER/'baseline/presentations/three_d'/name).read_text())
        new = methods((OWNER/'candidate/presentations/three_d'/name).read_text())
        facts[name] = dict(unchangedMethods=sorted(k for k in old.keys() & new.keys() if old[k] == new[k]),
                          changedMethods=sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
                          addedMethods=sorted(new.keys() - old.keys()), removedMethods=sorted(old.keys() - new.keys()))
        assert not facts[name]['removedMethods']
        if name == 'card_3d.gd':
            assert facts[name]['unchangedMethods'] == ['configure','corners','lift']
            assert facts[name]['changedMethods'] == ['_box','_ready']
        else:
            assert facts[name]['changedMethods'] == ['_add_card','_exit_tree','_show_cards']
            assert facts[name]['addedMethods'] == ['_create_card']
            for method in ['_add_card','_show_cards']:
                assert new[method] == old[method].replace('Card3D.new()', '_create_card()')
            assert new['_exit_tree'].replace('\n\t_card_resources = null', '') == old['_exit_tree']
    mentions = []
    for path in sorted(source_paths):
        if Path(path).suffix not in {'.gd','.tscn','.tres','.godot'}:
            continue
        for i,line in enumerate((OWNER/'candidate'/path).read_text().splitlines(),1):
            if any(term in line for term in ['Card3D', 'card_3d.gd', '_card_resources', '_shared_resources']):
                mentions.append(dict(path=path,line=i,text=line))
    assert len([m for m in mentions if 'Card3D.new()' in m['text']]) == 1
    assert all(m['path'] in changes for m in mentions)
    result = dict(verifiedUtc=datetime.now(timezone.utc).isoformat(), ownerRoot=str(OWNER), pins=pins,
                  filesVerified=155, unchangedFiles=153, exactChangedFiles=differences,
                  allBaselineFilesAlsoMatchDiagnosticHead=True, reconstructedPatchExactlyMatches=True,
                  files=records, methodComparisons=facts, constructionAndResourceReferences=mentions,
                  scope='Independent source/patch verification. No engine execution; dynamic runtime behavior is audited from owner originals separately.')
    target = ROOT/'candidate-source-review.json'
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(sha256=sha(target.read_bytes()),methodComparisons=facts),indent=2))


if __name__ == '__main__':
    main()
