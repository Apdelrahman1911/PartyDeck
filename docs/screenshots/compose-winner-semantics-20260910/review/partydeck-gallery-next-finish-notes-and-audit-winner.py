"""Finish retained visual notes and audit four existing JVM winner captures.

Reads evidence and source only; does not build, run the app, or invoke Git.
All outputs are outside the tracked gallery.
"""
import copy
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

REPO = Path('/root/projects/PartyDeck')
TMP = Path('/tmp')
ROOT = REPO / 'artifacts/evidence-storage/winner-semantics-validation-20260910'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def identity(path, **extra):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path),
            'bytes': path.stat().st_size, **extra}


older = read(TMP / 'partydeck-gallery-next-ios-34473325295-visual-notes.json')
latest = {
    'run': '34478720554',
    'review_method': 'All 43 new originals visually inspected in 15 internal review sheets outside the gallery before this note file was written. The failed 2D/200% launch has no original PNG; later decoded video frames are separate supplemental evidence.',
    'authority': [
        {
            'summary': '2D/200% fails the XCTest launch timeout with no original PNG and no initial application measurement. The original SQLite issue text and recording remain evidence of that failed case. Later decoded video frames do not replace a missing original capture or qualify native scene entry.',
            'notes': [],
        },
        copy.deepcopy(older['authority'][1]),
        {
            'summary': '3D/200% fails its current-diagnostic predicate after input: the rejected running observation remains revealed with selectedCount 0. The later failure capture visibly shows Selected Moon and measures selectedCount 1; it does not satisfy the earlier 15-second wait.',
            'notes': [
                'Back, Show hand, Star table and Your turn are readable. The wide seat roster is horizontally clipped and the lower 3D table lies mostly below the initial scroll viewport.',
                'The later failure PNG shows Selected Moon and readable Crown rows with Hide hand fixed above. The 3D cards are clipped above the scrolled list, while later rows and Play remain below the viewport. This later selected state is separate from the rejected selectedCount 0 observation.',
            ],
        },
        {
            'summary': 'Normal 3D fails its current-diagnostic predicate after input: the rejected running observation is still concealed. The later failure frame and measurement are revealed with selectedCount 0, without qualifying the failed 15-second wait.',
            'notes': [
                'All five card backs, Show hand and the disabled Select cards action fit. Star table and Your turn are readable; the roster extends horizontally beyond the viewport.',
                'The later failure PNG shows five unselected revealed faces with Moon, Crown, Crown, Star and Star captions. Hide hand fits and Select cards remains disabled. This later reveal does not satisfy the earlier rejected concealed observation.',
            ],
        },
        copy.deepcopy(older['authority'][4]),
    ],
    'retained': [
        {
            'summary': 'The background case passes its exact dormant Home/activate checkpoint, then fails the separate 60-second second-3D entry wait. The rejected observation is warming with the privacy cover and no renderer diagnostics; the later failure capture shows a concealed 3D table. No old-handle probe result follows from its visible test control.',
            'notes': copy.deepcopy(older['retained'][0]['notes'][:7]) + [
                'The actual dormant Home screen and Safari/Messages dock are visible without game content. Original endpoint evidence verifies the subsequent dormant Home/activate checkpoint; the later second-3D entry wait fails separately.',
                'The later failure PNG shows a concealed 3D table, complete Show hand and disabled Select cards. The native test header includes Old handle, without establishing an executed probe. The earlier rejected entry observation remains warming and covered.',
            ],
        },
        copy.deepcopy(older['retained'][1]),
        {
            'summary': 'The stale reentry case fails its 15-second diagnostic wait while warming with the privacy cover and no renderer diagnostics. The recorded wait takes 22.417283 seconds with a 21.349328-second query. A later measurement and PNG show a running concealed table after the cover was removed; this does not qualify the failed wait or an old-handle probe.',
            'notes': [
                'The later failure PNG shows a concealed 3D table with complete Show hand and disabled Select cards. The earlier rejected observation remains warming and covered with no renderer diagnostics; the later image cannot qualify that deadline or the old-handle probe.',
            ],
        },
    ],
}
latest['retained'][0]['notes'][4] = 'The actual Home screen and Safari/Messages dock are visible without game content; raw application-state observations remain separate evidence.'
audit = read(TMP / 'partydeck-gallery-next-ios-34478720554-source-audit.json')
assert [len(c['notes']) for c in latest['authority']] == [0, 11, 2, 2, 1]
assert [len(c['notes']) for c in latest['retained']] == [9, 17, 1]
for suite in audit['suites']:
    assert len(suite['cases']) == len(latest[suite['suite']])
    for case, notes in zip(suite['cases'], latest[suite['suite']]):
        assert len(case['capture_files']) == len(notes['notes'])
write_new(TMP / 'partydeck-gallery-next-ios-34478720554-visual-notes.json', latest)

receipt = read(ROOT / 'receipt.json')
assert receipt['exitCode'] == 0
assert receipt['command'] == ['xvfb-run', '-a', './gradlew', '--console=plain', ':composeApp:jvmTest', '--tests', 'dev.partydeck.app.GameplayLayoutTest']
xml_path = ROOT / 'TEST-dev.partydeck.app.GameplayLayoutTest.xml'
xml = ET.parse(xml_path).getroot()
assert xml.attrib == receipt['suite']
assert xml.attrib['tests'] == '7'
assert all(xml.attrib[key] == '0' for key in ['failures', 'errors', 'skipped'])
assert len(xml.findall('testcase')) == 7
assert not xml.findall('.//failure') and not xml.findall('.//error') and not xml.findall('.//skipped')
log = (ROOT / 'gradle.log').read_text()
assert '\n> Task :composeApp:jvmTest\n' in log
assert 'BUILD SUCCESSFUL in 17s' in log
assert '\n> Task :composeApp:compileKotlinJvm\n' in log
assert '\n> Task :composeApp:compileTestKotlinJvm\n' in log

source_dir = TMP / 'partydeck-gallery-next-winner-source'
source_dir.mkdir(exist_ok=False)
sources = []
for relative, expected in receipt['source'].items():
    source = REPO / relative
    assert sha(source) == expected, relative
    frozen = source_dir / relative
    frozen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, frozen)
    assert sha(frozen) == sha(source) == expected, relative
    sources.append(identity(frozen, relative_path='source/' + relative,
                            source_repository_path=relative,
                            source_copied_from=str(source),
                            receipt_source_sha256=expected,
                            artifact_type='later source copy matching the original execution receipt'))

source = (source_dir / 'composeApp/src/jvmTest/kotlin/dev/partydeck/app/GameplayLayoutTest.kt').read_text()
production = (source_dir / 'composeApp/src/commonMain/kotlin/dev/partydeck/app/ui/game/GameResults.kt').read_text()
testcases = {case.attrib['name'].removesuffix('[jvm]'): case.attrib for case in xml.findall('testcase')}
fixtures = [
    ('fifthCardAndPrivateHandControlsWorkOnNarrowPhone', 360, 640, 1, 'game-phone'),
    ('handAndResultsRemainUsableAtLargeText', 320, 740, 2, 'game-large-text'),
    ('handAndResultsRemainUsableOnShortLandscapePhone', 844, 390, 1, 'game-landscape'),
    ('handAndResultsRemainUsableInTabletWindow', 1024, 768, 1, 'game-tablet'),
]
for name, width, height, scale, prefix in fixtures:
    assert name in testcases
    expected = f'fun {name}() = qualifyGame({width}, {height}, {scale}f, "{prefix}")'
    assert expected in source, expected
assert 'File("build/ui-snapshots/$prefix-$suffix.png")' in source
assert 'capture("winner")' in source
assert 'val winnerText = "Alexandria Longname wins."' in source
assert 'winnerNodeId, winner.id' in source
assert 'winner.config.contains(SemanticsProperties.Heading)' in source
assert 'LiveRegionMode.Polite, winner.config[SemanticsProperties.LiveRegion]' in source
assert 'onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsProperties.LiveRegion)).assertCountEquals(1)' in source
assert source.count('assertStableWinnerAnnouncement()') == 5
assert 'pending = PendingAction.RETURN_TO_LOBBY' in source
assert 'onNodeWithText(finalVerdict).fetchSemanticsNode().config.contains(SemanticsProperties.LiveRegion)' in source
assert 'assertEquals(true, rematched)' in source
assert 'if (showReveal) ChallengeResult(view, outcome, largeText, Modifier.fillMaxWidth(), announceVerdict = false)' in production
assert 'stringResource(Res.string.game_winner_name, playerName(view, view.winnerId))' in production
assert 'liveRegion = LiveRegionMode.Polite' in production

captures = []
for name, width, height, scale, prefix in fixtures:
    path = ROOT / 'ui-snapshots' / (prefix + '-winner.png')
    with Image.open(path) as picture:
        picture.load()
        assert picture.format == 'PNG'
        assert picture.size == (width, height), (path, picture.size)
    captures.append(identity(
        path, relative_path=path.name, original_filename=path.name,
        scenario=f'Named winner — {prefix.removeprefix("game-").replace("-", " ")}',
        width_px=width, height_px=height, font_scale=float(scale),
        source_revision=None, source_revision_exact=False, ci_run=None,
        source_generation_path='build/ui-snapshots/' + path.name,
        test_name=name, test_result='passed',
        receipt_source=str(ROOT / 'receipt.json'), test_result_source=str(xml_path),
        platform='Compose JVM/Skiko layout fixture under Xvfb; density 1',
    ))
evidence = [identity(ROOT / name, relative_path='evidence/' + name,
                     artifact_type='original executed JVM validation evidence')
            for name in ['receipt.json', 'gradle.log', xml_path.name]] + sources
winner = {
    'schema_version': 1,
    'audit_kind': 'independent existing source, XML, log and PNG read; no new app or test execution',
    'completed_at': datetime.now(timezone.utc).isoformat(),
    'source_directory': str(ROOT),
    'original_receipt': receipt,
    'source_revision': None, 'source_revision_exact': False,
    'source_scope': 'Two later source copies exactly match hashes recorded by the original execution receipt. No exact whole-tree capture revision is asserted.',
    'executed_test_results': testcases,
    'focused_capture_count': 4,
    'captures': captures,
    'evidence_files': evidence,
    'verified_behavior_scope': [
        'Seven recorded JVM tests pass with no failures, errors or skips; jvmTest executes rather than being reported UP-TO-DATE.',
        'Four executed fixture methods each reach the real engine-projected named winner and write their own winner original at the recorded dimensions and font scale.',
        'The named-winner semantics node remains stable with heading and one polite live region during pending lobby controls and final-reveal open/close.',
        'The expanded final reveal adds no second live region; the return-to-lobby callback executes.',
    ],
    'limits': [
        'JVM rendering and semantics fixtures do not execute native VoiceOver or TalkBack.',
        'The retained directory contains 77 PNGs, including older subdirectories; only these four executed winner outputs are selected here. The rest are not claimed as freshly generated by this receipt.',
        'No exact clean whole-tree source revision is recorded.',
    ],
    'audit_script': identity(__file__),
}
write_new(TMP / 'partydeck-gallery-next-winner-source-audit.json', winner)
print(json.dumps({'latest_ios_notes': sum(len(c['notes']) for s in ['authority', 'retained'] for c in latest[s]),
                  'winner_captures': len(captures), 'winner_evidence_inputs': len(evidence)}, indent=2))
