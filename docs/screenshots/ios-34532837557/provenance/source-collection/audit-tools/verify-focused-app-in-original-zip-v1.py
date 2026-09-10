"""Audit each complete app tarball in the original ZIP without extracting a second copy."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import struct
import tarfile
import zipfile

BASE = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34532837557')
SOURCE = BASE.parent / 'source-e4871e1/source-e4871e1'
ARTIFACT = (BASE / 'ios-focused-production-reports-and-simulator-app').resolve()
RUN = 34532837557
HEAD = 'e4871e165f949c600ddd89b13e74d06fc34d2e04'
RUNNER = '/Users/runner/work/PartyDeck/PartyDeck/'


def read(path):
    return json.loads(path.read_bytes())


def record(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}


def same_content(actual, expected):
    assert actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256']


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, size=-1):
        data = self.stream.read(size)
        self.digest.update(data)
        self.bytes += len(data)
        return data

    def tell(self):
        return self.bytes


def macho(prefix):
    assert len(prefix) >= 32
    magic, cpu, subtype, kind, commands, command_bytes, flags, reserved = struct.unpack_from('<8I', prefix)
    assert magic == 0xfeedfacf and cpu == 0x0100000c and kind == 2
    assert 32 + command_bytes <= len(prefix)
    position, platforms = 32, []
    for _ in range(commands):
        command, size = struct.unpack_from('<2I', prefix, position)
        assert size >= 8 and position + size <= 32 + command_bytes
        if command == 0x32:
            platform, minimum, sdk, tools = struct.unpack_from('<4I', prefix, position + 8)
            platforms.append({'platform': platform, 'minimumOsEncoded': minimum, 'sdkEncoded': sdk})
        position += size
    assert position == 32 + command_bytes
    assert len(platforms) == 1 and platforms[0]['platform'] == 7
    return {'magic': 'MH_MAGIC_64', 'cpu': 'arm64', 'fileType': 'MH_EXECUTE',
            'buildVersionCommands': platforms, 'loadCommands': commands}


integrity_path = BASE / 'ios-focused-production-reports-and-simulator-app.integrity.json'
integrity = read(integrity_path)
assert integrity['runId'] == RUN and integrity['headSha'] == HEAD
archive = Path(integrity['archivePath'])
same_content(record(archive), {'bytes': integrity['archiveBytes'],
                             'sha256': integrity['archiveDigest'].removeprefix('sha256:')})
omitted = {row['path']: row for row in read(BASE / 'ios-focused-production-reports-and-simulator-app.unextracted-members.json')}
engine_path = ARTIFACT / 'godot/ios-host/build/evidence/engine-artifact.json'
module_path = ARTIFACT / 'godot/ios-host/build/evidence/native-module-inputs.json'
engine, module = read(engine_path), read(module_path)
assert engine['engine_commit'] == 'ed1daf0bf001b61586d9930840f2f1394092c079'
assert engine['simulator'] is True and engine['architecture'] == 'arm64'
assert engine['configuration'] == 'Debug' and engine['sdk'] == 'iphonesimulator'
assert engine['native_module_sources'] == module['native_module_sources']
assert engine['module_snapshot_sha256'] == module['module_snapshot_sha256']
native_sources = []
for relative, expected_hash in engine['native_module_sources'].items():
    item = record(SOURCE / 'godot/ios-host/modules' / relative)
    assert item['sha256'] == expected_hash
    native_sources.append(item)
assert len(native_sources) == 9
assert next(row['sha256'] for row in native_sources if row['path'].endswith('/PDGodotRuntime.mm')) == '7cb5038ad7b6a7d0c2446d83aefed94a835b1c77e328996558e87a5ebc909b1b'

cases = [
    ('production-sessions', 'build/ci/ios/godot-session/PartyDeck-session-simulator.app.tar.gz',
     'build/ci/ios/godot-session/godot-production-session-link.json',
     'build/ci/ios/godot-session/DerivedData/Build/Products/Debug-iphonesimulator/PartyDeckGodotInputs/inputs.json'),
]
apps = []
with zipfile.ZipFile(archive) as package:
    for scope, member_name, link_name, inputs_name in cases:
        link_path, inputs_path = ARTIFACT / link_name, ARTIFACT / inputs_name
        link, inputs = read(link_path), read(inputs_path)
        assert link['inputs'] == inputs
        assert inputs['engine_receipt'] == engine
        same_content(record(engine_path), inputs['engine_receipt_file'])
        assert inputs['native_pack_sha256'] == inputs['pack']['sha256'] == '541ded4c5074b56a9e320882a23f357ff8162520fac099e32567ac3a678f2751'
        assert link['macho']['architectures'] == ['arm64'] and link['macho']['platform'] == '7'
        source_plist = inputs['activation']['source_plist']
        assert source_plist['path'].startswith(RUNNER)
        same_content(record(SOURCE / source_plist['path'].removeprefix(RUNNER)), source_plist)
        members, captured = [], {}
        with package.open(member_name) as zipped:
            hashed = HashingReader(zipped)
            with gzip.GzipFile(fileobj=hashed, mode='rb') as compressed:
                with tarfile.open(fileobj=compressed, mode='r|') as tar:
                    for member in tar:
                        safe = PurePosixPath(member.name)
                        assert not safe.is_absolute() and '..' not in safe.parts
                        item = {'path': member.name, 'bytes': member.size, 'type': member.type.decode('ascii'),
                                'mode': oct(member.mode)}
                        if member.isfile():
                            payload = tar.extractfile(member)
                            digest, size, prefix = hashlib.sha256(), 0, bytearray()
                            keep_prefix = member.name in ('PartyDeck.app/PartyDeck', 'PartyDeck.app/Info.plist')
                            while chunk := payload.read(1024 * 1024):
                                digest.update(chunk)
                                size += len(chunk)
                                if keep_prefix and len(prefix) < 131072:
                                    prefix.extend(chunk[:131072 - len(prefix)])
                            assert size == member.size
                            item['sha256'] = digest.hexdigest()
                            if keep_prefix:
                                captured[member.name] = bytes(prefix)
                        elif member.issym() or member.islnk():
                            item['linkTarget'] = member.linkname
                        else:
                            assert member.isdir()
                        members.append(item)
                while compressed.read(1024 * 1024):
                    pass
            while hashed.read(1024 * 1024):
                pass
            tar_record = {'zipMember': member_name, 'bytes': hashed.bytes,
                          'sha256': hashed.digest.hexdigest(), 'storage': 'member of intact original ZIP'}
        same_content(tar_record, omitted[member_name])
        assert len({item['path'] for item in members}) == len(members)
        by_name = {item['path']: item for item in members}
        same_content(by_name['PartyDeck.app/PartyDeck'], link['executable'])
        same_content(by_name['PartyDeck.app/Info.plist'], link['app_info_plist'])
        actual_macho = macho(captured['PartyDeck.app/PartyDeck'])
        info = plistlib.loads(captured['PartyDeck.app/Info.plist'])
        assert info['CFBundleIdentifier'] == 'dev.partydeck.app'
        profile = info.get('PartyDeckGodotActivationProfile', 'shipping')
        accepted = info.get('PartyDeckQualifiedGodotPresentations', [])
        requested = info.get('PartyDeckQualificationGodotPresentations', [])
        actual_activation = {'profile': profile, 'accepted_shipping_modes': accepted,
                             'qualification_modes': requested,
                             'configured_enabled_native_modes': requested if profile == 'qualification' else accepted}
        assert actual_activation == link['packaged_activation'] == inputs['activation']['configuration']
        assert profile == ('qualification' if scope == 'production-sessions' else 'shipping')
        assert actual_activation['configured_enabled_native_modes'] == (['2d', '3d'] if scope == 'production-sessions' else [])
        for relative, expected in inputs['resource_files'].items():
            same_content(by_name['PartyDeck.app/ProbeResources/' + relative], expected)
        apps.append({'scope': scope, 'archiveMember': tar_record, 'originalLinkReceipt': record(link_path),
                     'originalInputs': record(inputs_path), 'members': members,
                     'allRegularMembersStreamedAndHashed': True, 'gzipStreamFullyConsumed': True,
                     'zipMemberCrcVerified': True, 'actualExecutable': by_name['PartyDeck.app/PartyDeck'],
                     'actualMachO': actual_macho, 'actualInfoPlist': by_name['PartyDeck.app/Info.plist'],
                     'actualPack': by_name['PartyDeck.app/ProbeResources/partydeck-last-light.pck'],
                     'actualPackagedActivation': actual_activation, 'resourceFilesMatched': len(inputs['resource_files']),
                     'nativeModuleInputsMatchExactSource': True})
        print(json.dumps({'scope': scope, 'tarMembers': len(members),
                          'actualExecutableBytes': link['executable']['bytes'], 'verified': True}), flush=True)

receipt = {
    'runId': RUN, 'headSha': HEAD, 'reviewedAtUtc': datetime.now(timezone.utc).isoformat(),
    'exactSourceBinding': record(BASE / 'exact-source-binding.json'),
    'originalZipIntegrity': record(integrity_path), 'originalArchive': record(archive),
    'physicalArchivePath': str(archive.resolve()),
    'originalEngineReceipt': record(engine_path), 'originalModuleInputs': record(module_path),
    'nativeSourceFilesIndependentlyVerified': native_sources, 'apps': apps,
    'productionAppArchivePreservedInsideCompleteZip': True,
    'duplicateAppTarballOrAppExtractionWritten': False,
    'scope': 'The focused production app tarball was streamed directly from the intact original ZIP, including gzip completion, ZIP CRC, every regular member hash, real arm64 iOS Simulator Mach-O headers, executable/Info.plist/resource/pack receipt equality and all nine native source hashes at e4871e1. The production app enables both explicit qualification modes. Actual packaged executable and PCK bytes are verified here; native .a hashes remain runner receipt evidence because the focused artifact contains engine build evidence rather than the standalone engine archives. XCTest outcomes, full Validate and physical-device/store acceptance remain separate.',
}
target = BASE / 'production-source-and-app-verification.json'
with target.open('x') as stream:
    stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'receipt': record(target), 'appsVerified': len(apps)}), flush=True)
