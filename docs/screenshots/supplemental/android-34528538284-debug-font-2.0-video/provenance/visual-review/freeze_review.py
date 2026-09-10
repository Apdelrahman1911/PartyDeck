import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/tmp/partydeck-video-review-34528538284-design-v1')
DECODER = Path('/tmp/partydeck-video-review-34528538284-root-v1')
RUNTIME = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34528538284/android-adaptive-api36-debug-font-2.0-34528538284-1/godot-adaptive/runtime')
PLAN = json.loads((BASE / 'review-plan.json').read_text())
OBS = [json.loads(line) for line in (BASE / 'direct-observations.jsonl').read_text().splitlines() if line.strip()]
NOW = datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity(path):
    path = Path(path)
    st = path.stat()
    return {'path': str(path), 'bytes': st.st_size, 'sha256': sha(path), 'mtimeNs': st.st_mtime_ns}

def write(name, value):
    path = BASE / name
    assert not path.exists(), str(path)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return identity(path)

assert len(OBS) == 122
assert sha(BASE / 'review-plan.json') == 'b311a836dbd90865ec85629b70662b14ad538648b5bae9b8c98d2fbb8f48f3ed'
assert sha(DECODER / 'decode-freeze.json') == PLAN['decoderFreeze']['sha256']
assert len({(o['clip'], o['derivativeSha256']) for o in OBS}) == 122
assert all(o['method'] == 'direct_full_frame_original_size_view_image' for o in OBS)
assert all(o['displayedDimensions'] == [1600, 720] for o in OBS)
assert all(o['privateCardFacesVisible'] is False for o in OBS)

targets = [
    ('observations/3d-landscape-held-control.xml', '714c8130e1b1ede502c44e0c43dee6a88a13a6877b43e9d42be3981d26c4001b'),
    ('observations/0027-held-target.log', '83aa9013936836bdacc7c42f30644b73404a7ff6c97f04850dff72cab82336b2'),
    ('observations/3d-landscape-concealed-before-up.xml', '3c7ededf997c3b8ff4ff481e7092131f3a29839468ca9363e92375d62a49541f'),
]
target_files = []
for relative, expected in targets:
    item = identity(RUNTIME / relative)
    assert item['sha256'] == expected
    item.update({'relativeRuntimePath': relative, 'physicalAlias': str((RUNTIME / relative).resolve())})
    target_files.append(item)
target_receipt = write('target-binding.json', {
    'schemaVersion': 1, 'recordedUtc': NOW, 'owner': '/root/review_design',
    'runId': PLAN['runId'], 'headSha': PLAN['headSha'],
    'files': target_files,
    'observedXmlTarget': {'hierarchyRotation': 1, 'class': 'android.widget.Button', 'text': 'Standard table',
        'contentDescription': 'Standard table. Continue this game with screen-reader controls.',
        'enabled': True, 'clickable': True, 'bounds': [150, 186, 826, 286], 'center': [488, 236],
        'resourceIdPresent': False, 'selector': 'text fallback'},
    'heldInputProof': {'window': '8c964b8 ...SessionGodotActivity', 'pid': 17141, 'uid': 10150,
        'pointer': 0, 'downTimeNs': 1116169000000, 'clock': 'InputDispatcher CLOCK_MONOTONIC',
        'commandSuppliedByAndroidReviewer': 'touchscreen display 0 swipe 488 236 488 236 30000'},
    'laterXml': {'hierarchyRotation': 0, 'resourceId': 'game-reveal-hand', 'enabled': True, 'clickable': True,
        'bounds': [63, 1472, 657, 1556]},
    'limits': [
        'The intended held target was Standard table. This scope does not test a card drag, Show hand hold or Back.',
        'Pixel review observes a lighter Standard table button; target identity comes from separate input/XML evidence.',
        'Display 0 and the clone display have different geometry/transforms. No cross-display mapping is inferred from the highlight.',
        'XML node bounds and visible clipped pixels are distinct evidence.',
        'Media timestamps are not bounded against InputDispatcher CLOCK_MONOTONIC; no per-frame before-UP assertion is made.'
    ]
})

findings = {
    '3d-landscape-rotation': [
        'Ready native landscape retains Last Light, ROUND 1, Show hand, Crown table, Your turn and the public Orbit claim. The hand and lower actions are below the font-2.0 viewport.',
        'Standard table is visibly lighter in frames 49–56; frame 57 is a sideways intermediate with a dark right portion.',
        'Frames 58–66 show centered portrait Closing table… and a privacy cover. Frame 67 shows the portrait cover only. From frame 70 the Standard portrait view shows a concealed five-card hand, while the lower Reveal/action area is clipped.',
        'The portrait image and black side areas occur inside the original fixed 1600 × 720 recording canvas.'
    ],
    '2d-split-entry': [
        'Native fullscreen readiness appears at frame 33. Exit, Your turn · Crown table and the upper 5 cards, covered. panel are visible; only a sliver of the lime reveal control reaches the lower edge.',
        'Frame 59 shows split entry: PartyDeck left with Closing table… and privacy cover; Android Display settings right. Frame 60 shows the left privacy cover alone.',
        'From frame 68, Standard in the left pane shows public Crown round-1 header and Set the tone. The hand and gameplay actions are offscreen; their concealed state is not directly observed.'
    ],
    '2d-split-exit': [
        'Initial Table style dialog is in the left pane with Display settings on the right.',
        'Native readiness at frame 36 shows Standard table, Leave table, Exit and the two-line Your turn · Crown table header. The hand and lower actions are below the left-pane viewport.',
        'Frame 51 shows fullscreen Closing table… with privacy cover after the second app disappears. Frame 57 shows privacy cover alone.',
        'From frame 60, Standard fullscreen shows public Crown round-1 header, Set the tone. and instruction. The hand and lower gameplay actions remain below the viewport; their concealed state is not directly observed.'
    ]
}
key_numbers = {'3d-landscape-rotation': [38, 49, 56, 57, 58, 67, 70, 88], '2d-split-entry': [33, 59, 60, 68, 80], '2d-split-exit': [36, 51, 57, 60, 65]}
clips = []
all_frame_records = []
for clip in PLAN['clips']:
    observations = [o for o in OBS if o['clip'] == clip['name']]
    by_sha = {o['derivativeSha256']: o for o in observations}
    groups = collections.defaultdict(list)
    for frame in clip['allFrames']:
        groups[frame['sha256']].append(frame['frameNumber'])
    assert set(groups) == set(by_sha)
    assert len(clip['allFrames']) == clip['original']['decodedFrameCount']
    frame_records = []
    for frame in clip['allFrames']:
        obs = by_sha[frame['sha256']]
        assert sorted(obs['byteIdenticalFrameNumbers']) == groups[frame['sha256']]
        representative = next(f for f in clip['allFrames'] if f['frameNumber'] == obs['frameNumber'])
        assert obs['frameIndex'] == representative['frameIndex']
        assert obs['mediaPts'] == representative['bestEffortTimestamp']
        assert obs['mediaPtsSeconds'] == representative['bestEffortTimestampSeconds']
        assert obs['derivativePath'] == representative['path']
        assert obs['originalSha256'] == clip['original']['sha256']
        is_direct = frame['frameNumber'] == obs['frameNumber']
        rec = dict(frame)
        rec.update({
            'clip': clip['name'], 'reviewStatus': 'direct_full_frame_view' if is_direct else 'reviewed_identical_bytes',
            'viewed': is_direct, 'reviewer': '/root/review_design', 'directRepresentativeFrameNumber': obs['frameNumber'],
            'directRepresentativePath': obs['derivativePath'], 'directObservationIndex': OBS.index(obs),
            'directObservationRecordedUtc': obs['recordedUtc'], 'state': obs['state'], 'observations': obs['observations'],
            'privateCardFacesVisible': False, 'mediaTimeBase': '1/90000',
            'sourceFileMtimeNs': Path(frame['path']).stat().st_mtime_ns,
            'byteIdentityScope': 'Findings apply to identical PNG bytes; capture/frame identities and presentation times remain distinct.'
        })
        frame_records.append(rec)
    clip_record = {
        'name': clip['name'], 'original': clip['original'], 'directViews': len(observations),
        'reviewedByteMatches': len(frame_records) - len(observations), 'decodedFrames': len(frame_records),
        'unviewedDecodedFrames': 0, 'visiblePrivateCardFaces': False, 'findings': findings[clip['name']],
        'keyFrames': [{k: f[k] for k in ['frameNumber', 'frameIndex', 'bestEffortTimestamp', 'bestEffortTimestampSeconds', 'sha256', 'state']} for f in frame_records if f['frameNumber'] in key_numbers[clip['name']]],
        'frameIdentities': frame_records
    }
    clips.append(clip_record)
    all_frame_records.extend(frame_records)

assert len(all_frame_records) == 233
assert sum(f['viewed'] for f in all_frame_records) == 122
assert len({f['path'] for f in all_frame_records}) == 233
assert len({f['sha256'] for f in all_frame_records}) == 122
review_receipt = write('review.json', {
    'schemaVersion': 1, 'recordedUtc': NOW, 'owner': '/root/review_design',
    'runId': PLAN['runId'], 'headSha': PLAN['headSha'], 'pckSha256': PLAN['expectedPckSha256'], 'pckBytes': PLAN['expectedPckBytes'],
    'directViews': 122, 'reviewedByteMatches': 111, 'decodedFrameIdentities': 233, 'unviewedDecodedFrames': 0,
    'directObservationReceipt': identity(BASE / 'direct-observations.jsonl'),
    'decoderFreeze': identity(DECODER / 'decode-freeze.json'), 'targetBinding': target_receipt,
    'method': PLAN['method'], 'timestampCautions': PLAN['timestampCautions'],
    'clockCaution': identity(BASE / 'clock-caution.json'),
    'clips': clips,
    'conclusion': 'No private card faces are visible in any of the 233 decoded PNG identities, covered by 122 direct full-size views and 111 identical-byte matches. Several hand controls remain outside the font-2.0 viewport.',
    'limits': [
        'This covers all decoded frame identities in these three recordings; it does not establish that every rendered device frame was captured.',
        'No continuous privacy or per-frame before-UP deadline qualification is asserted. Host UTC, media PTS, Winscope elapsed time and InputDispatcher CLOCK_MONOTONIC have no bounded cross-clock mapping here.',
        'Native scope outcomes are separate from visual observations. XML visible/enabled flags do not prove whole controls fit the captured viewport.',
        'The held target was Standard table. Card dragging, Back and other input targets are outside this scope.',
        'The two lower-priority successful 2D rotation recordings were not decoded or reviewed by this task.',
        'This review is bound to the exact old head/PCK above; it does not qualify current main, the new PCK, Android native large-text corrections or unrelated missing footage.'
    ],
    'publicationRequirement': 'Publish every one of the 233 PNG derivatives as a labeled supplement, retaining its own identity and PTS; preserve each original MP4 separately. Do not reopen completed images solely for publication.'
})
validation_receipt = write('validation.json', {
    'schemaVersion': 1, 'recordedUtc': NOW, 'status': 'passed',
    'reviewPlan': identity(BASE / 'review-plan.json'), 'review': review_receipt,
    'directObservationRecords': len(OBS), 'uniqueDirectClipHashGroups': len({(o['clip'], o['derivativeSha256']) for o in OBS}),
    'frameIdentitiesCoveredExactlyOnce': len(all_frame_records), 'directViews': 122, 'reviewedIdenticalByteMatches': 111,
    'allFrameMetadataAndRepresentativesAgree': True, 'allDirectViewsOriginalSize': [1600, 720],
    'priorDecoderValidationReused': {'filesVerified': 249, 'pngsVerifiedWithPillow': 233, 'sha256BoundByReviewPlan': PLAN['decoderFreeze']['sha256']},
    'checksNow': 'Verified frozen plan/decode receipt hashes and three target files; validated exact frame coverage, SHA groups, derivative/original identities, frame indices and media times against completed direct observation records. Decoder payload validation is reused; no image was reopened or decoded.'
})
freeze_names = ['review-plan.json', 'direct-observations.jsonl', 'clock-caution.json', '3d-landscape-summary.json', 'target-binding.json', 'review.json', 'validation.json', 'freeze_review.py', 'record_review.py']
freeze = write('freeze.json', {
    'schemaVersion': 1, 'frozenAtUtc': NOW, 'status': 'completed-visual-review-ready-for-publication',
    'owner': '/root/review_design', 'files': [identity(BASE / n) for n in freeze_names],
    'externalDecoderFreeze': identity(DECODER / 'decode-freeze.json'),
    'coverage': {'directViews': 122, 'reviewedByteMatches': 111, 'decodedFrames': 233},
    'scope': 'Three original Android 34528538284 debug font-2.0 recordings; exact 8030efe head and 557b2297 PCK. No native/current-main upgrade.'
})
print(json.dumps({'freeze': freeze, 'review': review_receipt, 'validation': validation_receipt}, indent=2))
