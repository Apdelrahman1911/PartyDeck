"""Preserve the exact invocation and output of an off-repository evidence auditor."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path('/tmp/partydeck-engine-ci/34473325295')
label, script, *arguments = sys.argv[1:]
assert '/' not in label and '..' not in label
script = Path(script).resolve()
script.relative_to((BASE / 'audit-tools').resolve())
directory = BASE / 'audit-commands'
directory.mkdir(exist_ok=True)
log = directory / (label + '.log')
receipt = directory / (label + '.json')
assert not log.exists() and not receipt.exists()
command = [sys.executable, '-u', '-B', str(script), *arguments]
started = datetime.now(timezone.utc).isoformat()
with log.open('xb') as output:
    result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=600)
document = {'command': command, 'startedAtUtc': started,
    'completedAtUtc': datetime.now(timezone.utc).isoformat(), 'exitCode': result.returncode,
    'log': {'path': str(log), 'bytes': log.stat().st_size,
        'sha256': hashlib.sha256(log.read_bytes()).hexdigest()},
    'auditorSha256': hashlib.sha256(script.read_bytes()).hexdigest()}
receipt.write_text(json.dumps(document, indent=2) + '\n')
print(log.read_text(errors='replace')[-16000:])
print(json.dumps({'commandReceipt': str(receipt), 'exitCode': result.returncode}), flush=True)
raise SystemExit(result.returncode)
