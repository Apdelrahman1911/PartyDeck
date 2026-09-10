"""Decode retained xcresult data objects and expose unchanged app output streams."""
from pathlib import Path
import ctypes
import ctypes.util
import hashlib
import json
import re
import sys

bundle, output = map(Path, sys.argv[1:3])
output.mkdir(parents=True, exist_ok=True)
lib = ctypes.CDLL(ctypes.util.find_library('zstd'))
lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
lib.ZSTD_decompress.restype = ctypes.c_size_t
lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
lib.ZSTD_isError.restype = ctypes.c_uint
lib.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]
lib.ZSTD_getErrorName.restype = ctypes.c_char_p
records, streams, crashes = [], [], []
for path in sorted((bundle / 'Data').glob('data.*')):
    raw = path.read_bytes()
    compressed = raw.startswith(bytes.fromhex('28b52ffd'))
    if compressed:
        source = ctypes.create_string_buffer(raw)
        capacity = 65536
        while True:
            destination = ctypes.create_string_buffer(capacity)
            size = lib.ZSTD_decompress(destination, capacity, source, len(raw))
            if not lib.ZSTD_isError(size):
                data = destination.raw[:size]
                break
            error = lib.ZSTD_getErrorName(size).decode()
            if 'Destination buffer is too small' not in error or capacity >= 536870912:
                raise RuntimeError(f'{path.name}: {error}')
            capacity *= 2
        decoded = output / (path.name + '.bin')
        decoded.write_bytes(data)
    else:
        data, decoded = raw, path
    item = {'source': str(path), 'sourceBytes': len(raw), 'sourceSha256': hashlib.sha256(raw).hexdigest(),
            'decoded': str(decoded), 'zstdDecoded': compressed, 'decodedBytes': len(data),
            'decodedSha256': hashlib.sha256(data).hexdigest()}
    if data.startswith(b'Standard output and standard error from'):
        app_log = output / f'app-stdout-stderr-{len(streams) + 1:03}.log'
        app_log.write_bytes(data)
        item['appOutputLog'] = str(app_log)
        streams.append(item)
    if b'"procName"' in data and (b'"exception"' in data or b'"termination"' in data):
        crashes.append(item)
    records.append(item)

aggregate = output / 'app-stdout-stderr.log'
with aggregate.open('wb') as target:
    for item in streams:
        target.write(Path(item['appOutputLog']).read_bytes())
        target.write(b'\n')
pattern = re.compile(r'\[ERROR\]|ERROR:|SCRIPT ERROR:|fatal|EXC_BAD|SIGABRT|terminating app|uncaught|Unhandled|assertion failed', re.I)
excerpts = []
for item in streams:
    lines = Path(item['appOutputLog']).read_text(errors='replace').splitlines()
    selected = set()
    for index, line in enumerate(lines):
        if pattern.search(line):
            selected.update(range(max(0, index - 2), min(len(lines), index + 4)))
    excerpts.extend([f"{Path(item['appOutputLog']).name}:{index + 1}: {lines[index]}" for index in sorted(selected)])
(output / 'app-error-excerpts.log').write_text('\n'.join(excerpts) + '\n')
receipt = {'scope': 'Read-only complete xcresult data-object decoding with system libzstd; original source files are unchanged.',
           'bundle': str(bundle), 'dataObjects': records, 'appStreams': streams, 'crashCandidates': crashes,
           'aggregateAppOutput': str(aggregate), 'errorExcerpts': str(output / 'app-error-excerpts.log')}
(output / 'decoded-object-index.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'objects': len(records), 'zstdObjects': sum(r['zstdDecoded'] for r in records),
                  'appStreams': len(streams), 'crashCandidates': len(crashes),
                  'appOutput': str(aggregate), 'errorExcerpts': str(output / 'app-error-excerpts.log')}, indent=2))
