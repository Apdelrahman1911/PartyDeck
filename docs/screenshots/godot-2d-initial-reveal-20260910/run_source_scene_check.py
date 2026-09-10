#!/usr/bin/env python3
"""Retain a focused run of the unchanged, repository-owned 2D scene checker."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

base = Path(__file__).resolve().parent
source = Path('/root/projects/PartyDeck/godot/renderer')
case = base / 'tracked-compact-scene-font-1.0'
case.mkdir(exist_ok=False)
capture = case / 'captures'
fixture = base / 'launch-font-1.0.json'
checker = source / 'presentations/two_d/checks/scene_check.gd'
engine = Path('/opt/partydeck-godot/godot')
command = [
    'xvfb-run', '-a', '-s', '-screen 0 1280x1800x24',
    str(engine), '--path', str(source), '--audio-driver', 'Dummy',
    '--rendering-method', 'gl_compatibility', '--rendering-driver', 'opengl3',
    '--script', str(checker), '--', '--manual-bridge',
    f'--check-output={capture}', f'--check-fixture={fixture}',
    '--check-width=411', '--check-height=711', '--check-text-scale=1',
    '--check-touch-drag=true', '--check-lobby=true',
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {
    'purpose': 'Existing compact 2D source scene input/privacy check; not native qualification.',
    'startedUtc': datetime.now(timezone.utc).isoformat(),
    'command': command,
    'environmentOverrides': {'LIBGL_ALWAYS_SOFTWARE': '1'},
    'inputs': [{
        'path': str(path), 'sha256': digest(path), 'sizeBytes': path.stat().st_size,
    } for path in [Path(__file__), checker, fixture, engine,
                   source / 'scripts/main.gd', source / 'presentations/two_d/table.gd']],
}
(case / 'invocation.json').write_text(json.dumps(receipt, indent=2) + '\n')
environment = os.environ.copy()
environment['LIBGL_ALWAYS_SOFTWARE'] = '1'
with (case / 'stdout.log').open('wb') as stdout, (case / 'stderr.log').open('wb') as stderr:
    try:
        result = subprocess.run(command, stdout=stdout, stderr=stderr,
                                env=environment, timeout=90, check=False)
        receipt['exitCode'] = result.returncode
    except subprocess.TimeoutExpired:
        receipt['exitCode'] = None
        receipt['timeoutSeconds'] = 90
logs = '\n'.join((case / name).read_text(errors='replace') for name in ['stdout.log', 'stderr.log'])
errors = [line for line in logs.splitlines()
          if re.search(r'\b(?:SCRIPT ERROR|ERROR|FATAL|Segmentation fault)\b', line)]
labels = ['01-concealed', '02-revealed-selected', '03-covered-again',
          '04-resumed-covered', '05-lobby-confirmation']
required = [f'{label}.{suffix}' for label in labels for suffix in ['png', 'json']] + ['report.json']
missing = [name for name in required if not (capture / name).is_file()]
report = {}
if (capture / 'report.json').is_file():
    report = json.loads((capture / 'report.json').read_text())
receipt.update({
    'finishedUtc': datetime.now(timezone.utc).isoformat(),
    'errors': errors,
    'missingEvidence': missing,
    'completed': receipt['exitCode'] == 0 and not errors and not missing and report.get('result') == 'passed',
    'evidence': [{
        'path': str(path.relative_to(case)), 'sha256': digest(path), 'sizeBytes': path.stat().st_size,
    } for path in sorted(case.rglob('*')) if path.is_file()],
})
(case / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'completed': receipt['completed'], 'errors': errors,
                  'missingEvidence': missing, 'reportResult': report.get('result'),
                  'inputObservations': [x for x in report.get('observations', []) if 'input' in x]}, indent=2))
if not receipt['completed']:
    print(logs)
    sys.exit(1)
