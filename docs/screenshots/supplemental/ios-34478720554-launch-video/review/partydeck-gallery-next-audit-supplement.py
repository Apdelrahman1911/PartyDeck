"""Audit the frozen nine-frame supplement; retain its original derivation scope."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from PIL import Image

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34478720554-2d200-launch-review')
TMP = Path('/tmp')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def identity(path, **extra):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path),
            'bytes': path.stat().st_size, **extra}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


expected = {
    'collection-frozen.json': '3b3fe85f89b59d2a8ccf3f67833007598a1b9e3b4f08149ecb572b70b8a458d3',
    'viewed-frames.json': 'bfdf12544668f82b779c3d1922cfb3b28c13a98a6218a347929d17c3d2a61fff',
    'decoded-frame-manifest.json': 'e4dcc60308f1e10f1bb2b14f3211ad8afd112b2542158fe1a32ac67caaf497b1',
    'RESULT.md': '4f2785d6b3e625a8f2a110a98c5801fec78e8591d0bea0452944f08d6c8b7418',
}
for name, digest in expected.items():
    assert sha(ROOT / name) == digest, name
freeze = read(ROOT / 'collection-frozen.json')
assert len(freeze['files']) == freeze['file_count_excluding_this_manifest'] == 160
assert sum(item['bytes'] for item in freeze['files']) == freeze['bytes_excluding_this_manifest']
assert {str(path.relative_to(ROOT)) for path in ROOT.rglob('*') if path.is_file()} == {
    item['path'] for item in freeze['files']} | {'collection-frozen.json'}
for item in freeze['files']:
    path = ROOT / item['path']
    assert path.stat().st_size == item['bytes'], item['path']
    assert sha(path) == item['sha256'], item['path']

decoded = read(ROOT / 'decoded-frame-manifest.json')
viewed = read(ROOT / 'viewed-frames.json')
original = decoded['original_video']
assert original['sha256'] == '399b9f05d4f06728d0709e16fd80a989ad81299a6985376aac8c62e774b2fa25'
assert Path(original['path']).stat().st_size == original['bytes'] == 1756068
assert sha(original['path']) == original['sha256']
assert decoded['frame_count'] == len(decoded['frames']) == 129
assert decoded['dimensions'] == [1206, 2622]
assert decoded['frame_time_base'] == '1/600'
assert len(viewed['frames']) == 9
assert {frame['file'] for frame in viewed['frames']} == {
    f'frames/frame-{index:04}.png' for index in [1, 2, 3, 25, 60, 72, 73, 100, 129]}
by_name = {frame['file']: frame for frame in decoded['frames']}
frames = []
for selected in sorted(viewed['frames'], key=lambda item: item['index_zero_based']):
    full = by_name[selected['file']]
    for key in ['bytes', 'sha256', 'index_zero_based', 'original_video_frame']:
        assert selected[key] == full[key], (selected['file'], key)
    path = ROOT / selected['file']
    with Image.open(path) as picture:
        picture.load()
        assert picture.format == 'PNG' and picture.size == (1206, 2622)
    frame = identity(path, relative_path=selected['file'],
                     original_filename=path.name,
                     artifact_type='derived_original_video_frame',
                     width_px=1206, height_px=2622,
                     original_ci_png=False, source_revision='c6ea1dd9f7966517fbee87a06b633d01c432c24d',
                     source_revision_exact=True, ci_run='34478720554',
                     original_video=copy.deepcopy(original),
                     transform=decoded['transform'], frame_time_base=decoded['frame_time_base'],
                     original_video_frame=copy.deepcopy(selected['original_video_frame']),
                     original_view_order=selected['view_order'],
                     original_individual_view_timestamp=selected['individual_view_timestamp'],
                     original_reviewer_observation=selected['observation'])
    frames.append(frame)
gap = Decimal(by_name['frames/frame-0073.png']['original_video_frame']['pts_time']) - Decimal(by_name['frames/frame-0072.png']['original_video_frame']['pts_time'])
assert gap == Decimal('3.501667')

# These are compact original review receipts and inputs, not newly generated media.
evidence = [identity(ROOT / item['path'], relative_path='evidence/' + item['path'],
                     artifact_type='frozen original video derivation evidence')
            for item in freeze['files'] if not item['path'].startswith('frames/')]
evidence.append(identity(ROOT / 'collection-frozen.json', relative_path='evidence/collection-frozen.json',
                         artifact_type='frozen supplemental collection inventory'))
evidence.append(identity(original['path'], relative_path='recording/' + Path(original['path']).name,
                         artifact_type='original CI screen recording',
                         original_ci_png=False, source_revision='c6ea1dd9f7966517fbee87a06b633d01c432c24d',
                         source_revision_exact=True, ci_run='34478720554'))
assert len(evidence) == 33
result = {
    'schema_version': 1,
    'audit_kind': 'independent frozen file, original video identity and selected PNG read; no decoding or native execution performed by this audit',
    'completed_at': datetime.now(timezone.utc).isoformat(),
    'source_directory': str(ROOT),
    'verified_frozen_files': len(freeze['files']),
    'original_video': original,
    'source_revision': 'c6ea1dd9f7966517fbee87a06b633d01c432c24d',
    'source_revision_exact': True, 'ci_run': '34478720554',
    'decoded_frame_count': 129, 'selected_derived_frame_count': 9,
    'original_ci_png_count': 0,
    'frames': frames, 'evidence_files': evidence,
    'pts_gap_between_consecutive_frames_72_and_73_seconds': str(gap),
    'absolute_pts_origin_resolved': False,
    'possible_origins_retained_without_choosing': ['2026-09-10T12:59:01Z (MP4 creation metadata)', '2026-09-10T12:59:02.094Z (recording attachment metadata)'],
    'limits': [
        'Decoded video frames are supplemental and excluded from original CI PNG totals.',
        'All 129 decoded frames were hash-verified; the nine selected frames were visually inspected by game_domain. Independent publication review is recorded separately.',
        'The recording shows the late Idle chooser; native scene entry and gameplay are not qualified.',
        'A start-2d tap attempt is logged, but delivery is not established. Absence of a Synthesize event activity does not prove that no input arrived.',
        '2D/200% names the failed test; chooser pixels do not establish enlarged text or a 200% renderer.',
        'The original launch failure remains failed. Neither late chooser pixels nor later source analysis establish an OS or debugger root cause.',
    ],
    'audit_script': identity(__file__),
}
write_new(TMP / 'partydeck-gallery-next-video-source-audit.json', result)
print(json.dumps({'verified_frozen_files': 160, 'derived_frames': len(frames),
                  'evidence_inputs': len(evidence), 'new_original_ci_pngs': 0}, indent=2))
