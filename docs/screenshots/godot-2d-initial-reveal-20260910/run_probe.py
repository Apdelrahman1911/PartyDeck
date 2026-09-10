#!/usr/bin/env python3
"""Run one isolated graphical layout case and retain every result unchanged."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('case')
parser.add_argument('--fixture', default='launch-font-1.0.json')
parser.add_argument('--source', default='frame-v1-source')
parser.add_argument('--height', default=1244, type=int)
args = parser.parse_args()
base = Path(__file__).resolve().parent
case = base / args.case
case.mkdir(exist_ok=False)
capture = case / 'captures'
source = base / args.source
fixture = base / args.fixture
script = base / 'initial_reveal_probe.gd'
engine = Path('/opt/partydeck-godot/godot')
command = [
    'xvfb-run', '-a', '-s', '-screen 0 1280x1800x24',
    str(engine), '--path', str(source), '--audio-driver', 'Dummy',
    '--rendering-method', 'gl_compatibility', '--rendering-driver', 'opengl3',
    '--resolution', f'720x{args.height}', '--script', str(script),
    '--', '--manual-bridge', f'--probe-output={capture}',
    f'--probe-fixture={fixture}', f'--probe-height={args.height}',
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {
    'case': args.case,
    'purpose': 'Isolated desktop rendering of native surface geometry; not Android qualification.',
    'startedUtc': datetime.now(timezone.utc).isoformat(),
    'command': command,
    'environmentOverrides': {'LIBGL_ALWAYS_SOFTWARE': '1'},
    'inputs': [{
        'path': str(path), 'sha256': digest(path), 'sizeBytes': path.stat().st_size,
    } for path in [Path(__file__), script, fixture, engine,
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
required = ['01-early.png', '01-early.json', '02-late.png', '02-late.json',
            'observations.json', 'bridge-events.jsonl']
missing = [name for name in required if not (capture / name).is_file()]
observations = []
if (capture / 'observations.json').is_file():
    observations = json.loads((capture / 'observations.json').read_text())
events = []
if (capture / 'bridge-events.jsonl').is_file():
    events = [json.loads(line) for line in (capture / 'bridge-events.jsonl').read_text().splitlines()]
receipt.update({
    'finishedUtc': datetime.now(timezone.utc).isoformat(),
    'errors': errors,
    'missingEvidence': missing,
    'observationCount': len(observations),
    'eventCount': len(events),
    'completed': receipt['exitCode'] == 0 and not errors and not missing and len(observations) == 2,
    'evidence': [{
        'path': str(path.relative_to(case)), 'sha256': digest(path), 'sizeBytes': path.stat().st_size,
    } for path in sorted(case.rglob('*')) if path.is_file()],
})
(case / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'case': args.case, 'completed': receipt['completed'],
                  'errors': errors, 'missingEvidence': missing, 'observations': observations}, indent=2))
if not receipt['completed']:
    print(logs)
    sys.exit(1)
