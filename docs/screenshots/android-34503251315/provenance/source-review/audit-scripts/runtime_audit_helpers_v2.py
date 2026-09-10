import json
from datetime import datetime
import re, struct, zlib

def png_dimensions(path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR'
    size, cursor, ended = struct.unpack_from('>II', data, 16), 8, False
    while cursor < len(data):
        length = struct.unpack_from('>I', data, cursor)[0]
        end = cursor + length + 12
        assert end <= len(data)
        kind, payload = data[cursor + 4:cursor + 8], data[cursor + 8:end - 4]
        assert zlib.crc32(kind + payload) & 0xffffffff == struct.unpack_from('>I', data, end - 4)[0]
        cursor = end
        if kind == b'IEND':
            assert not payload and cursor == len(data)
            ended = True
    assert ended
    return list(size)

def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def exact_app_processes(raw):
    lines = [line for line in raw.decode('utf-8', errors='strict').splitlines() if line.strip()]
    assert lines[0].split() == ['PID', 'UID', 'NAME']
    rows = {}
    for line in lines[1:]:
        fields = line.split(None, 2)
        assert len(fields) == 3 and re.fullmatch('[0-9]+', fields[0]) and re.fullmatch('[0-9]+', fields[1])
        pid, uid, name = int(fields[0]), int(fields[1]), fields[2]
        assert pid > 0 and pid not in rows
        rows[pid] = {'pid': pid, 'uid': uid, 'name': name}
    return [row for row in rows.values() if row['name'] in ('dev.partydeck.app', 'dev.partydeck.app:godot')]

def focused_activity(text):
    # Independently read the focused Resumed: record on the default display;
    # topResumedActivity and historical ActivityRecords are not focus evidence.
    display, found = None, []
    for line in text.splitlines():
        header = re.match(r'^Display #(\d+) \(activities from top to bottom\):', line)
        if header:
            display = int(header[1])
        if display != 0 or not re.match(r'^\s+Resumed:\s', line):
            continue
        match = re.search(r'ActivityRecord\{[^ ]+ u(\d+) ([^ ]+) t(\d+)(?:\s|\})', line)
        assert match, line
        package, activity = match[2].split('/', 1)
        component = package + '/' + (package + activity if activity.startswith('.') else activity)
        found.append({'user_id': int(match[1]), 'component': component,
                      'task_id': int(match[3]), 'display_id': 0})
    unique = {json.dumps(row, sort_keys=True): row for row in found}
    assert len(unique) == 1, found
    return next(iter(unique.values()))
