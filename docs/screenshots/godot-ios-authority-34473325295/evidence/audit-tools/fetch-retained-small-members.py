"""Read selected original ZIP members by ranges while the full ZIP is collected."""
from datetime import datetime, timezone
from pathlib import Path
import ctypes
import ctypes.util
import hashlib
import io
import json
import sqlite3
import subprocess
import urllib.error
import urllib.request
import zipfile

BASE = Path('/tmp/partydeck-engine-ci/34473325295')
OUTPUT = BASE / 'early-retained-members'
OUTPUT.mkdir()
BLOCKS = OUTPUT / 'range-blocks'
BLOCKS.mkdir()
ARTIFACT = next(item for item in json.loads((BASE / 'artifacts.json').read_text())['artifacts']
                if item['name'] == 'godot-ios-retained-host-test-attempt-1')
assert ARTIFACT['workflow_run']['id'] == 34473325295
assert ARTIFACT['workflow_run']['head_sha'] == '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d'
ENDPOINT = f"https://api.github.com/repos/Apdelrahman1911/PartyDeck/actions/artifacts/{ARTIFACT['id']}/zip"


def sha(data): return hashlib.sha256(data).hexdigest()
def record(path): return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


credential = subprocess.run(['gh', 'auth', 'token'], capture_output=True, check=True).stdout.decode().strip()
request = urllib.request.Request(ENDPOINT, headers={'Authorization': 'Bearer ' + credential,
    'Accept': 'application/vnd.github+json', 'User-Agent': 'PartyDeck-evidence-collector'})
try:
    response = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
except urllib.error.HTTPError as response:
    assert response.code == 302, f'Unexpected artifact redirect status: {response.code}'
    download_url = response.headers['Location']
else:
    response.close()
    raise RuntimeError('Expected a redirect to the original artifact ZIP.')
del credential, request


class OriginalZipRanges(io.RawIOBase):
    def __init__(self):
        self.position = 0
        self.length = ARTIFACT['size_in_bytes']
        self.records = []
        self.cache = {}
        self.etag = None

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset
        assert 0 <= self.position <= self.length
        return self.position

    def read(self, count=-1):
        if count < 0: count = self.length - self.position
        count = min(count, self.length - self.position)
        if count == 0: return b''
        assert count <= 8 * 1024 * 1024, 'Refuse an unexpectedly large selected-member read.'
        if count <= 65536:
            start = self.position // 65536 * 65536
            end = min(self.length, ((self.position + count + 65535) // 65536) * 65536)
        else:
            start, end = self.position, self.position + count
        key = (start, end)
        if key not in self.cache:
            req = urllib.request.Request(download_url, headers={'Range': f'bytes={start}-{end-1}',
                'Accept-Encoding': 'identity', 'User-Agent': 'PartyDeck-evidence-collector'})
            with urllib.request.urlopen(req, timeout=45) as response:
                assert response.status == 206, 'Original artifact server did not honor a byte range.'
                expected = f'bytes {start}-{end-1}/{self.length}'
                assert response.headers['Content-Range'] == expected
                data = response.read()
                etag = response.headers.get('ETag')
            assert len(data) == end - start
            if self.etag is None: self.etag = etag
            assert etag == self.etag
            self.cache[key] = data
            path = BLOCKS / f'{start}-{end-1}.bin'
            path.write_bytes(data)
            self.records.append({'start': start, 'endInclusive': end-1, 'contentRange': expected,
                'etag': etag, **record(path)})
        result = self.cache[key][self.position-start:self.position-start+count]
        self.position += count
        return result


remote = OriginalZipRanges()
members = []
PREFIX = 'retained-host-test/artifacts/'
with zipfile.ZipFile(remote) as package:
    def member(name):
        info = package.getinfo(name)
        path = OUTPUT / 'members' / name
        assert '..' not in Path(name).parts and not Path(name).is_absolute()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = package.read(name)
        assert len(data) == info.file_size
        path.write_bytes(data)
        members.append({'zipMember': name, 'zipCrc32': f'{info.CRC:08x}', 'zipCrcVerified': True,
            'compressedBytes': info.compress_size, 'localHeaderOffset': info.header_offset, **record(path)})
        return path

    manifest_path = member(PREFIX + 'attachments/manifest.json')
    database_path = member(PREFIX + 'RetainedHost.xcresult/database.sqlite3')
    manifest = json.loads(manifest_path.read_text())
    connection = sqlite3.connect('file:' + str(database_path) + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    attachment_rows = {row['uuid']: dict(row) for row in connection.execute(
        'SELECT uuid,name,xcResultKitPayloadRefId FROM Attachments')}
    selected = []
    for case in manifest:
        if not any(name in case['testIdentifier'] for name in ['BackgroundTransitions', 'StaleFirstReady']): continue
        for attachment in case['attachments']:
            if attachment['exportedFileName'].endswith('.json'):
                selected.append((case['testIdentifier'], attachment))
    lib = ctypes.CDLL(ctypes.util.find_library('zstd'))
    lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    lib.ZSTD_isError.restype = ctypes.c_uint
    lib.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]
    lib.ZSTD_getErrorName.restype = ctypes.c_char_p
    payloads = []
    for identifier, attachment in selected:
        path = member(PREFIX + 'attachments/' + attachment['exportedFileName'])
        row = attachment_rows[path.stem]
        original = member(PREFIX + 'RetainedHost.xcresult/Data/data.' + row['xcResultKitPayloadRefId'])
        raw = original.read_bytes()
        compressed = raw.startswith(bytes.fromhex('28b52ffd'))
        decoded = raw
        if compressed:
            source = ctypes.create_string_buffer(raw)
            capacity = 65536
            while True:
                output = ctypes.create_string_buffer(capacity)
                size = lib.ZSTD_decompress(output, capacity, source, len(raw))
                if not lib.ZSTD_isError(size):
                    decoded = output.raw[:size]
                    break
                error = lib.ZSTD_getErrorName(size).decode()
                assert 'Destination buffer is too small' in error and capacity < 16 * 1024 * 1024, error
                capacity *= 2
        assert decoded == path.read_bytes(), 'Attachment differs from original XCResult payload.'
        payload = {'testIdentifier': identifier, 'attachment': attachment, 'attachmentFile': record(path),
            'originalXcresultObject': record(original), 'originalPayloadRefId': row['xcResultKitPayloadRefId'],
            'zstdDecoded': compressed, 'matchesOriginalXcresultPayload': True}
        payloads.append(payload)
        print(json.dumps({'event': 'original-payload-matched', 'name': attachment['suggestedHumanReadableName'],
            'file': str(path), 'sha256': sha(decoded)}), flush=True)

receipt = {'runId': 34473325295, 'headSha': '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d',
    'recordedAtUtc': datetime.now(timezone.utc).isoformat(), 'artifactId': ARTIFACT['id'],
    'artifactApiDigest': ARTIFACT['digest'], 'artifactApiBytes': ARTIFACT['size_in_bytes'],
    'apiEndpoint': ENDPOINT, 'wholeArtifactApiDigestVerifiedHere': False,
    'scope': 'Provisional selected original ZIP members via authenticated GitHub redirect and consistent byte ranges. ZIP CRC and XCResult payload equality verified. Whole-ZIP API SHA-256 correlation follows when complete collection finishes.',
    'rangeBlocks': remote.records, 'members': members, 'matchedOriginalPayloads': payloads,
    'manifest': record(manifest_path), 'xcresultDatabase': record(database_path)}
receipt_path = OUTPUT / 'range-member-evidence.json'
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'event': 'range-collection-complete', 'receipt': record(receipt_path),
    'matchedPayloads': len(payloads), 'downloadedRangeBytes': sum(item['bytes'] for item in remote.records)}), flush=True)
