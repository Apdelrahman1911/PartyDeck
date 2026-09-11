#!/usr/bin/env python3
"""Private, serialized executions using the existing real renderer tools and engine."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
REPOSITORY = Path('/root/projects/PartyDeck')
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(REPOSITORY / 'godot/tools'))
spec = importlib.util.spec_from_file_location('partydeck_renderer_tool', REPOSITORY / 'godot/tools/renderer.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def resources():
    info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return {'utc': datetime.now(timezone.utc).isoformat(),
            'memAvailableBytes': int(info['MemAvailable'].split()[0]) * 1024,
            'destinationFreeBytes': shutil.disk_usage(WORK).free,
            'checkoutFreeBytes': shutil.disk_usage(REPOSITORY).free}

def check_resources():
    result = resources()
    # Resource-policy admission: 3 GiB floor + 768 MiB engine reserve + 32 MiB output.
    if result['memAvailableBytes'] < 4_060_086_272 or result['destinationFreeBytes'] < 1_107_296_256:
        raise RuntimeError('Resource floor failed: ' + json.dumps(result))
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['import', 'layout', 'scene', 'scene-original', 'redraw'])
    parser.add_argument('project', choices=['baseline', 'candidate'])
    parser.add_argument('name')
    parser.add_argument('--fixture', default='ordinary-claim-launch.json')
    parser.add_argument('--width', type=int, default=681)
    parser.add_argument('--height', type=int, default=377)
    parser.add_argument('--density', type=float, default=1.75)
    parser.add_argument('--text-scale', type=float, default=2.0)
    parser.add_argument('--expect', default='observe')
    parser.add_argument('--touch-drag', action='store_true')
    args = parser.parse_args()
    output = WORK / 'runs' / args.name
    if output.exists():
        raise RuntimeError('Use a fresh run name; evidence is immutable after execution.')
    output.mkdir()
    project = WORK / (args.project + '-project')
    source_before = renderer.source_snapshot(project)
    commands = renderer.Commands(output)
    lock_path = '/tmp/partydeck-godot.lock'
    lock = open(lock_path, 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = check_resources()
    engine = renderer.engine_info(REPOSITORY / 'godot/qualification/build/toolchain/godot')
    error = None
    external_inputs = []
    try:
        if args.operation == 'import':
            renderer.import_and_check(engine, project, commands)
        else:
            script = {'layout': 'context_layout_probe.gd', 'scene': 'density_scene_check.gd',
                      'scene-original': 'three_d_scene_check.gd', 'redraw': 'three_d_redraw_check.gd'}[args.operation]
            harness = WORK / 'inputs' / script
            for input_path in [harness, WORK / 'inputs' / 'three_d_scene_check.gd',
                               WORK / 'inputs' / args.fixture, Path(__file__).resolve()]:
                external_inputs.append({'path': str(input_path), 'bytes': input_path.stat().st_size,
                                        'sha256': hashlib.sha256(input_path.read_bytes()).hexdigest()})
            argv = ['xvfb-run', '-a', '-s', '-screen 0 1280x1600x24', engine['executable'],
                    '--path', str(project), '--rendering-method', 'gl_compatibility',
                    '--display-driver', 'x11', '--audio-driver', 'Dummy',
                    '--resolution', f'{args.width}x{args.height}', '--position', '0,0',
                    '--script', str(harness), '--', '--manual-bridge', '--presentation=3d',
                    '--check-output=' + str(output), '--check-fixture=' + str(WORK / 'inputs' / args.fixture),
                    '--check-width=' + str(args.width), '--check-height=' + str(args.height),
                    '--check-density=' + str(args.density), '--check-text-scale=' + str(args.text_scale),
                    '--check-expect=' + args.expect]
            if args.touch_drag:
                argv.append('--check-touch-drag=true')
            commands.run('godot', argv, project, timeout=90)
    except Exception as exc:
        error = str(exc)
    after = resources()
    fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()
    source_after = renderer.source_snapshot(project)
    if source_after['fingerprint'] != source_before['fingerprint']:
        error = (error or '') + ' Runtime inputs changed during the run.'
    captures = []
    for image in sorted(output.glob('*.png')):
        entry = {'path': str(image), 'bytes': image.stat().st_size,
                 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
        captures.append(entry)
    result = {'operation': args.operation, 'arguments': vars(args), 'project': str(project),
              'engine': engine, 'sourceBefore': source_before, 'sourceAfter': source_after,
              'externalInputs': external_inputs,
              'resourceLock': lock_path, 'resourcesBefore': before, 'resourcesAfter': after,
              'admission': {'memAvailableFloorWithReserve': 4_060_086_272,
                            'destinationFloorWithReserve': 1_107_296_256,
                            'engineWorkingReserveBytes': 768 * 1024**2,
                            'totalOutputBoundBytes': 32 * 1024**2},
              'commands': commands.records, 'captures': captures, 'error': error}
    (output / 'run-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'run': str(output), 'error': error, 'captures': len(captures),
                      'memAvailableAfter': after['memAvailableBytes']}, indent=2))
    return 1 if error else 0

if __name__ == '__main__':
    sys.exit(main())
