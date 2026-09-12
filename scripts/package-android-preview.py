#!/usr/bin/env python3
"""Verify and stage the exact debug preview APK after its emulator smoke passes."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import android_godot_activation as activation

ROOT = Path(__file__).resolve().parents[1]
ANDROID = '{http://schemas.android.com/apk/res/android}'
NATIVE_CHECKS = {'package-inputs', 'installation', 'display', '3d.engine-practice-baseline',
                 '3d.engine-reveal-selection', '3d.engine-play-standard-outcome', '3d.engine-leave-end'}
RENDER_CHECKS = {'redraw', 'play_effect', 'quality_capture'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_preview_reports(apk_hash, pack_hash, source):
    reports = ROOT / 'build/ci/android-preview'
    smoke = json.loads((reports / 'runtime/smoke-result.json').read_text())
    require(smoke.get('passed') is True and smoke.get('apkSha256') == apk_hash,
            'This exact APK did not pass Standard preview smoke.')
    native = json.loads((reports / 'godot-3d/smoke-result.json').read_text())
    checks = native.get('checks')
    require(native.get('passed') is True and native.get('apkSha256') == apk_hash
            and native.get('sourceRevision') == source and native.get('requestedModes') == ['3d']
            and isinstance(checks, dict) and set(checks) == NATIVE_CHECKS
            and all(isinstance(check, dict) and check.get('status') == 'passed' for check in checks.values()),
            'This exact APK/source did not pass every required native 3D preview check.')
    rendering = json.loads((reports / 'renderer/check-result.json').read_text())
    cases = rendering.get('cases')
    require(rendering.get('passed') is True and rendering.get('rendererPackSha256') == pack_hash
            and isinstance(cases, list) and len(cases) == len(RENDER_CHECKS)
            and all(isinstance(case, dict) and case.get('passed') is True
                    and type(case.get('assertions')) is int and case['assertions'] > 0 for case in cases)
            and {case.get('name') for case in cases} == RENDER_CHECKS,
            'The embedded renderer did not pass the 3D resolution, feedback and redraw checks.')
    return smoke, native, rendering


def main():
    os.chdir(ROOT)
    source = os.environ['GITHUB_SHA']
    run_id, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    require(re.fullmatch(r'[0-9a-f]{40}', source), 'Expected the exact source commit.')
    require(run_id.isdecimal() and attempt.isdecimal(), 'Expected numeric workflow identity.')
    checked_out = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    require(checked_out == source, 'The checked-out source differs from the workflow commit.')
    apk = ROOT / 'androidApp/build/outputs/apk/debug/androidApp-debug.apk'
    pack = ROOT / 'godot/qualification/build/renderer/partydeck-last-light.pck'
    output = ROOT / 'build/android-preview-release'
    output.mkdir(parents=True, exist_ok=False)
    reports = ROOT / 'build/ci/android-preview/package'
    reports.mkdir(parents=True, exist_ok=True)
    sdk_tools = Path(os.environ['ANDROID_HOME']) / 'build-tools/36.0.0'

    def checked(argv, name):
        result = subprocess.run([str(arg) for arg in argv], capture_output=True, timeout=180)
        (reports / (name + '.stdout.log')).write_bytes(result.stdout)
        (reports / (name + '.stderr.log')).write_bytes(result.stderr)
        require(result.returncode == 0, f'{name} failed; inspect the retained package report.')
        return result.stdout

    signature = checked([sdk_tools / 'apksigner', 'verify', '--verbose', '--print-certs', apk], 'signature')
    certificates = re.findall(rb'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$', signature, re.M)
    require(len(certificates) == 1, 'Expected one verified APK signer.')
    checked([sdk_tools / 'zipalign', '-c', '-P', '16', '-v', '4', apk], 'alignment')
    analyzer = shutil.which('apkanalyzer')
    require(analyzer, 'Android SDK apkanalyzer is unavailable.')
    manifest_bytes = checked([analyzer, 'manifest', 'print', apk], 'manifest')
    expected = activation.parse_build_expectation((ROOT / 'build/ci/android/godot-activation-build.json').read_bytes())
    packaged = activation.parse_packaged_manifest(manifest_bytes)
    activation.require_qualification_match(expected, packaged, '2d,3d')
    manifest = ET.fromstring(manifest_bytes)
    application = manifest.find('application')
    require(application.get(ANDROID + 'debuggable') == 'true', 'This workflow publishes an explicitly debug build.')
    activities = application.findall('activity')
    launcher = [item for item in activities if item.get(ANDROID + 'name') in ('.MainActivity', 'dev.partydeck.app.MainActivity')]
    require(len(launcher) == 1 and launcher[0].get(ANDROID + 'exported') == 'true', 'Missing full-app launcher.')
    require(any(
        intent.find("action[@" + ANDROID + "name='android.intent.action.MAIN']") is not None
        and intent.find("category[@" + ANDROID + "name='android.intent.category.LAUNCHER']") is not None
        for intent in launcher[0].findall('intent-filter')), 'Missing MAIN/LAUNCHER intent.')
    for tag, suffix in (('activity', 'godot.SessionGodotActivity'), ('service', 'godot.GodotSessionBrokerService')):
        entries = [item for item in application.findall(tag) if item.get(ANDROID + 'name') in ('.' + suffix, 'dev.partydeck.app.' + suffix)]
        require(len(entries) == 1 and entries[0].get(ANDROID + 'exported') == 'false', f'Expected private {suffix}.')
    checked(['python3', '-B', 'godot/tools/renderer.py', 'check-pack', '--pack', pack], 'source-pack')
    pack_hash = digest(pack)
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        require(names.count('assets/partydeck-last-light.pck') == 1, 'Expected one embedded renderer pack.')
        require('lib/arm64-v8a/libgodot_android.so' in names, 'Missing Godot native library for ARM64 phones.')
        with archive.open('assets/partydeck-last-light.pck') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pack_hash, 'Embedded renderer pack differs from source.')
    apk_hash = digest(apk)
    smoke, native, rendering = verified_preview_reports(apk_hash, pack_hash, source)
    shipped_apk = output / 'PartyDeck-android-preview.apk'
    shutil.copyfile(apk, shipped_apk)
    require(digest(shipped_apk) == apk_hash, 'Staged APK differs from the checked APK.')
    metadata = {
        'sourceCommit': source, 'workflowRunId': run_id, 'workflowAttempt': attempt,
        'package': 'dev.partydeck.app', 'variant': 'debug', 'signing': 'Android debug identity',
        'certificateSha256': certificates[0].decode().lower(), 'apkSha256': apk_hash,
        'apkBytes': shipped_apk.stat().st_size, 'rendererPackSha256': pack_hash,
        'activation': packaged, 'initialPresentation': 'Standard',
        'versionName': manifest.get(ANDROID + 'versionName'),
        'versionCode': manifest.get(ANDROID + 'versionCode'), 'smoke': smoke,
        'godotSmoke': native, 'rendererChecks': rendering,
        'physicalDeviceQualification': False, 'productionQualified': False,
    }
    (output / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
    repository = os.environ['GITHUB_REPOSITORY']
    notes = f'''Install **PartyDeck-android-preview.apk** from the assets below on an Android phone (Android 8.0 or later).

This is the full PartyDeck app with practice, hosting and joining. **Standard table** is selected initially; enter a game and use **Table style** to try **2D table** and **3D table**.

The 3D table now renders at display resolution, fits its full rim on screen, and uses smooth card and table-symbol edges. Accepted card plays from you and other players get a short face-down card animation and a placement sound. Sound and Reduce Motion settings remain available.

For multiplayer, everyone needs this build and the same reachable Wi-Fi network. The host must keep the app open. Practice works without other phones.

This is a debug-signed test preview. Android may ask you to allow installation from your browser or file manager. If an older PartyDeck build has a different signing key, uninstall it before installing this one; uninstalling clears local settings. These CI debug keys are not retained for guaranteed updates.

The workflow passed its configured JVM tests/lint, verified the signature, alignment and both-mode renderer package, and exercised Standard and native 3D practice with this exact APK in a 1080×2400 API36 emulator. The exported renderer also passed desktop checks for display-density sizing, table containment, play feedback, privacy and idle redraw. Real-phone multiplayer, speaker output, accessibility and performance remain under testing. This is not a production release.

Report problems at https://github.com/{repository}/issues with your phone model, Android version, chosen table style and steps to reproduce. Do not post live invitations or private hand contents.

Source: `{source}`. Build: https://github.com/{repository}/actions/runs/{run_id} (attempt {attempt}).

`SHA256SUMS` verifies the APK, build metadata and these release notes. `build-info.json` records the source, signer and executed smoke scope.
'''
    (output / 'RELEASE-NOTES.md').write_text(notes)
    files = (shipped_apk, output / 'build-info.json', output / 'RELEASE-NOTES.md')
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in files))
    print(json.dumps({'apk': shipped_apk.name, 'bytes': shipped_apk.stat().st_size, 'sha256': apk_hash, 'source': source}))


if __name__ == '__main__':
    main()
