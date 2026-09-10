#!/usr/bin/env python3
"""Reuse verified safe UI captures and run new authority cases against compiled Kotlin artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

TOOLS = Path(__file__).resolve().parent
ROOT = Path('/root/projects/PartyDeck')
FROZEN = Path('/tmp/partydeck-2d-captures/iteration-04')
IMPORT_NAMES = ('six-long-names', 'observer', 'three-card-proof', 'eliminated-active-round', 'forced-challenge')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(directory):
    return {p.name: sha(p) for p in sorted(directory.glob('*.json'))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('/tmp/partydeck-godot-edge-fixtures'))
    args = parser.parse_args()
    output = args.output.resolve()
    canonical = ROOT / 'godot/bridge/fixtures'
    assert output != canonical and not output.is_relative_to(canonical)
    before = hashes(canonical)
    receipt = json.loads((FROZEN / 'source-provenance.json').read_text())
    imports = TOOLS / 'imports'
    imports.mkdir(exist_ok=True)
    for name in IMPORT_NAMES:
        source = FROZEN / 'fixtures' / f'{name}.json'
        assert sha(source) == receipt['fixtures'][source.name], source
        shutil.copyfile(source, imports / source.name)
    for name in ('PartyDeck2DEdgeFixtures.java', 'source-provenance.json'):
        shutil.copyfile(FROZEN / name, imports / name)

    artifacts = [ROOT / f'godot/qualification/build/modules/{name}/libs/{name}-jvm.jar' for name in ('core', 'games', 'bridge')]
    cache = Path('/root/.gradle/caches/modules-2/files-2.1')
    for group, name, version in (
        ('org.jetbrains.kotlin', 'kotlin-stdlib', '2.4.20'),
        ('org.jetbrains.kotlinx', 'kotlinx-serialization-core-jvm', '1.11.0'),
        ('org.jetbrains.kotlinx', 'kotlinx-serialization-json-jvm', '1.11.0'),
    ):
        matches = list((cache / group / name / version).glob('*/*.jar'))
        assert len(matches) == 1, (name, matches)
        artifacts += matches
    assert all(p.is_file() for p in artifacts)
    artifact_hashes = {str(p): sha(p) for p in artifacts}
    classes = TOOLS / 'classes'
    classes.mkdir(exist_ok=True)
    classpath = ':'.join(map(str, artifacts))
    compile_command = ['javac', '-cp', classpath, '-d', str(classes), str(TOOLS / 'CompleteEdgeFixtures.java')]
    subprocess.run(compile_command, check=True)
    output.mkdir(parents=True, exist_ok=True)
    run_command = ['java', '-cp', f'{classes}:{classpath}', 'CompleteEdgeFixtures', str(imports), str(output)]
    result = subprocess.run(run_command, check=True, text=True, capture_output=True)
    (output / 'generation.log').write_text(result.stdout + result.stderr)
    print(result.stdout, end='')
    assert artifact_hashes == {str(p): sha(p) for p in artifacts}, 'Compiled artifact changed during generation'

    provenance_path = output / 'authority-provenance.json'
    provenance = json.loads(provenance_path.read_text())
    fixtures = {}
    for case in provenance['cases']:
        pair = [json.loads((output / name).read_text()) for name in case['files']]
        assert pair[0]['presentationMode'] == '2d' and pair[1]['presentationMode'] == '3d'
        assert {k: v for k, v in pair[0].items() if k != 'presentationMode'} == {k: v for k, v in pair[1].items() if k != 'presentationMode'}
        assert set(pair[0]['payload']) == {'game', 'controls'}
        fixtures.update({name: sha(output / name) for name in case['files']})
    assert len(fixtures) == 20
    after = hashes(canonical)
    assert after == before, 'Canonical fixture bytes changed during generation'
    manifest = {
        'version': 1,
        'purpose': 'Separate reproducible authority-backed scene cases for both UI owners; not live multiplayer evidence',
        'generator': {'source': str(TOOLS / 'CompleteEdgeFixtures.java'), 'sha256': sha(TOOLS / 'CompleteEdgeFixtures.java')},
        'runner': {'source': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__).resolve())},
        'importSource': {'source': str(imports / 'PartyDeck2DEdgeFixtures.java'), 'sha256': sha(imports / 'PartyDeck2DEdgeFixtures.java')},
        'importReceipt': {'source': str(imports / 'source-provenance.json'), 'sha256': sha(imports / 'source-provenance.json')},
        'importedFixturesSha256': {f'{name}.json': sha(imports / f'{name}.json') for name in IMPORT_NAMES},
        'compiledArtifactsSha256': artifact_hashes,
        'artifactBasis': 'Actual precompiled qualification artifacts used at execution; no Gradle invocation or source-rebuild claim',
        'compileCommand': compile_command,
        'runCommand': run_command,
        'canonicalFixturesUnchanged': True,
        'canonicalManifestSha256': before['fixture-manifest.json'],
        'authorityProvenanceSha256': sha(provenance_path),
        'checks': ['original import hashes match ui_shell receipt', 'imported 2D launch bytes unchanged', 'bridge safe-view schema round trip', 'both modes differ only by presentationMode', 'bounded real authority case predicates', 'compiled artifacts unchanged during execution', 'canonical fixture bytes unchanged'],
        'coverage': {
            'sixSeatsLongDuplicateNames': 'six-long-names', 'oneCardHand': 'one-card-hand',
            'zeroCardNonEliminatedHand': 'zero-card-hand', 'forcedChallenge': 'forced-challenge',
            'eliminatedSpectatorInActiveRound': 'eliminated-active-round', 'unknownObserver': 'observer',
            'truthfulMatchingRank': 'truthful-rank', 'truthfulWild': 'truthful-wild',
            'bluffThreeCardPublicProof': 'three-card-proof', 'burnoutRoundEnded': 'burnout',
            'activeHostReturnToLobby': 'six-long-names',
        },
        'sha256': fixtures,
    }
    manifest_path = output / 'fixture-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print('Manifest SHA-256:', sha(manifest_path))


if __name__ == '__main__':
    main()
