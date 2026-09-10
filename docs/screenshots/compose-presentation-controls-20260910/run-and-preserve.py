from pathlib import Path
import fcntl
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

repo = Path('/root/projects/PartyDeck')
base = Path('/tmp/partydeck-common-presentation-ui')
output = base / 'iteration-02'
output.mkdir(exist_ok=False)
command = ['./gradlew', ':composeApp:jvmTest', '--tests', 'dev.partydeck.app.PresentationLayoutTest', '--console=plain']
with Path('/tmp/partydeck-gradle.lock').open('a') as lock:
    print('Waiting for the shared Gradle lock', flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)
    print('Acquired shared lock; running the focused UI checks', flush=True)
    snapshots = repo / 'composeApp/build/ui-snapshots'
    before = set(snapshots.glob('presentation-*'))
    with (output / 'test.log').open('w') as log:
        result = subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT)
    result_path = repo / 'composeApp/build/test-results/jvmTest/TEST-dev.partydeck.app.PresentationLayoutTest.xml'
    if result_path.exists():
        shutil.copyfile(result_path, output / 'test-results.xml')
    for folder in sorted(set(snapshots.glob('presentation-*')) - before):
        shutil.copytree(folder, output / folder.name)
    (output / 'command.json').write_text(json.dumps({'command': command, 'exitCode': result.returncode}, indent=2) + '\n')
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    suite = ET.parse(output / 'test-results.xml').getroot()
    assert suite.attrib['tests'] == '2' and suite.attrib['failures'] == '0' and suite.attrib['errors'] == '0'
    print('Both tests pass; exact XML and all new screenshots archived before lock release', flush=True)

source_paths = [
    'composeApp/src/commonMain/kotlin/dev/partydeck/app/PartyDeckApp.kt',
    'composeApp/src/commonMain/kotlin/dev/partydeck/app/ui/shell/GameplayPresentationControls.kt',
    'composeApp/src/commonMain/composeResources/values/presentation_strings.xml',
    'composeApp/src/jvmTest/kotlin/dev/partydeck/app/PresentationLayoutTest.kt',
]
for name in source_paths:
    destination = base / 'source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / name, destination)
shutil.copyfile('/tmp/partydeck-session-ui-radio-button.html', base / 'radio-button-source.html')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {
    'purpose': 'Common app presentation selector and Compose fallback qualification',
    'testResult': suite.attrib,
    'sourceSha256': {name: sha(repo / name) for name in source_paths},
    'controllerApiSource': 'composeApp/src/commonMain/kotlin/dev/partydeck/app/controller/GameplayPresentationState.kt',
    'controllerApiSha256': sha(repo / 'composeApp/src/commonMain/kotlin/dev/partydeck/app/controller/GameplayPresentationState.kt'),
    'behavior': 'Only available modes offered; 2D, 3D and Standard choices reachable at 200% text; OPENING and ACTIVE contain no game/private card nodes; CLOSING/COMPOSE retain the same SessionView and pending action, conceal the hand and require a fresh selection. UI passes fontScale to the controller, keeps shell Rules/Settings routes and localizes labels.',
    'repeatReason': 'Initial test passed but another filtered task removed its shared XML before archival. Initial observed result, complete log and all four original PNGs preserved; second result archived while holding the shared Gradle lock.',
    'limitations': 'Real Compose/Skia JVM rendering of explicit shell lifecycle fixtures and real core-safe GameView projections. No native factory is faked or instantiated; not Android/iOS execution or native accessibility/attachment qualification. Platform native fallback controls are owned separately.',
    'filesSha256': {str(p.relative_to(base)): sha(p) for p in sorted(base.rglob('*')) if p.is_file()},
}
(base / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Provenance SHA-256:', sha(base / 'provenance.json'), flush=True)
