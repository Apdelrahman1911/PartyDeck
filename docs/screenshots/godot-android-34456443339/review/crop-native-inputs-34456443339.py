"""Derive unchanged-pixel crops from captured controls matching the next real tap."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

BASE = Path('/tmp/partydeck-engine-ci/34456443339')
sys.path.insert(0, str(BASE / 'source-dad1c11/godot/android-checks'))
from evidence import read_png


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def encode_png(rgb, width, height):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    stride = width * 3
    assert len(rgb) == stride * height
    rows = b''.join(b'\0' + rgb[offset:offset + stride] for offset in range(0, len(rgb), stride))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


OUTPUT = BASE / 'input-target-crops'
OUTPUT.mkdir(exist_ok=False)
records = []
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        artifact = BASE / f'godot-android-{mode}-font-{scale}-debug'
        directory = artifact / f'android/runtime/{mode}/match'
        original = directory / '02-revealed.png'
        capture = read(directory / '02-revealed.json')
        diagnostic = capture['diagnostics']
        inputs = lines(directory / 'scene-input-geometry.log')
        observations = lines(directory / 'host-observations.log')
        input_line, item = next((number, item) for number, item in enumerate(inputs, 1)
                               if item['action'] == 'tap' and item['group'] == 'partydeck_hand_card' and item['cardIndex'] == 0)
        assert item['revision'] == capture['revision'] == '0'
        assert item['presentationId'] == capture['presentationId']
        assert item['engineSurface'] == capture['engineSurface']
        assert item['rootViewport'] == diagnostic['viewport']
        assert int(item['diagnosticSequence']) == int(diagnostic['sequence']) + 1
        controls = [control for control in diagnostic['controls'] if all(
            control[key] == item[key] for key in ['group', 'cardIndex', 'rect', 'clipRect'])]
        assert len(controls) == 1 and controls[0]['visible']
        input_snapshots = [host for host in observations if 'diagnostics' in host
                           and host['diagnostics']['sequence'] == item['diagnosticSequence']
                           and host['diagnostics']['requestId'] == item['diagnosticRequest']]
        assert input_snapshots
        assert all(host['publicState'] == capture['publicState'] and host['revision'] == capture['revision']
                   and host['presentationId'] == capture['presentationId'] and host['enginePid'] == capture['enginePid']
                   and not host['diagnostics']['handConcealed'] and host['diagnostics']['selectedCount'] == 0
                   for host in input_snapshots)
        assert not diagnostic['handConcealed'] and diagnostic['selectedCount'] == 0
        surface, viewport, rect, clip = item['engineSurface'], item['rootViewport'], item['rect'], item['clipRect']
        left, top = max(0, rect[0], clip[0]), max(0, rect[1], clip[1])
        right = min(viewport['width'], rect[0] + rect[2], clip[0] + clip[2])
        bottom = min(viewport['height'], rect[1] + rect[3], clip[1] + clip[3])
        box = [math.ceil(surface['x'] + left * surface['width'] / viewport['width']),
               math.ceil(surface['y'] + top * surface['height'] / viewport['height']),
               math.floor(surface['x'] + right * surface['width'] / viewport['width']),
               math.floor(surface['y'] + bottom * surface['height'] / viewport['height'])]
        x, y = item['coordinates']['x'], item['coordinates']['y']
        assert box[0] <= x < box[2] and box[1] <= y < box[3]
        pixel_rect = {'x': box[0], 'y': box[1], 'width': box[2] - box[0], 'height': box[3] - box[1]}
        original_crop = read_png(original.read_bytes()).crop(pixel_rect)
        output = OUTPUT / f'{mode}-font-{scale}-first-card-target.png'
        output.write_bytes(encode_png(original_crop, pixel_rect['width'], pixel_rect['height']))
        assert original_crop == read_png(output.read_bytes()).rgb
        records.append({
            'artifact': artifact.name,
            'wholeCasePassed': read(artifact / 'android/runtime/result.json')['passed'],
            'originalPath': str(original), 'originalSha256': digest(original),
            'captureHostPath': str(directory / '02-revealed.json'), 'captureHostSha256': digest(directory / '02-revealed.json'),
            'captureDiagnosticSequence': diagnostic['sequence'], 'captureDiagnosticRequest': diagnostic['requestId'],
            'inputGeometryPath': str(directory / 'scene-input-geometry.log'),
            'inputGeometrySha256': digest(directory / 'scene-input-geometry.log'), 'inputGeometryLine': input_line,
            'input': item,
            'matchingCaptureControl': controls[0],
            'samePresentationRevisionSurfaceViewportAndTargetGeometry': True,
            'sameRevealedUnselectedHandState': True,
            'pixelCropRect': pixel_rect,
            'output': {'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
                       'width': pixel_rect['width'], 'height': pixel_rect['height'],
                       'rgbSha256': hashlib.sha256(original_crop).hexdigest()},
            'unchangedOriginalCropPixelsVerified': True,
            'scope': 'The retained revealed frame precedes the tap by one diagnostic refresh. Target geometry and state match, but this is not a separately captured per-input screenshot.',
        })

receipt = {'runId': 34456443339, 'headSha': 'dad1c11741bd4322bb8b2afb9f18f3db5f50c919',
           'derivedCropCount': len(records), 'crops': records,
           'directVisualReviewStatus': 'Pending actual image inspection; pixel derivation alone makes no visual-review claim.'}
with (BASE / 'input-target-crop-receipt.json').open('x') as stream:
    stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'crops': [item['output'] for item in records]}, indent=2))
