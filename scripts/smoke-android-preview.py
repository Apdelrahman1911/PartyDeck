#!/usr/bin/env python3
"""Run existing installation/Home and Standard practice checks for a preview APK."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'partydeck_preview_ui_smoke', Path(__file__).with_name('smoke-android-ui.py'))
ui_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ui_smoke
spec.loader.exec_module(ui_smoke)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with args.apk.open('rb') as stream:
        apk_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    smoke = ui_smoke.AndroidSmoke(args.serial, args.output, 'debug-preview')
    result = {'passed': False, 'apkSha256': apk_hash, 'steps': smoke.steps,
              'scope': 'API36 emulator installation, cold launch, Home and Standard practice; '
                       'Godot interaction, physical phones and LAN multiplayer remain separate.'}
    try:
        if smoke.adb('shell', 'getprop', 'ro.build.version.sdk').strip() != '36':
            raise RuntimeError('Preview smoke requires the API36 emulator.')
        smoke.setup(args.apk)
        smoke.practice()
        result['passed'] = True
    except Exception as error:
        result['error'] = ui_smoke.redacted(str(error))
        result['stage'] = smoke.stage
        raise
    finally:
        try:
            smoke.diagnostics()
            diagnostic_errors = sorted(path.name for path in args.output.glob('*.error.log'))
            if diagnostic_errors or not (args.output / 'final-screen.png').is_file():
                raise RuntimeError(f'Incomplete preview diagnostics: {diagnostic_errors or ["final-screen.png missing"]}')
        except Exception as error:
            result['passed'] = False
            result['diagnosticError'] = ui_smoke.redacted(str(error))
        finally:
            try:
                errors = smoke.restore_environment()
            except Exception as error:
                errors = [str(error)]
            if errors:
                result['passed'] = False
                result['restoreErrors'] = [ui_smoke.redacted(error) for error in errors]
            (args.output / 'smoke-result.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['passed']:
        raise SystemExit('Preview smoke diagnostics or restoration failed.')
    print('Preview installation, Home and Standard practice passed.')


if __name__ == '__main__':
    main()
