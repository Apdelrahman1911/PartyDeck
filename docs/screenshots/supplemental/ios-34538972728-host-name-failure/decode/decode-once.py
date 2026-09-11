#!/usr/bin/env python3
"""One admitted decode of the original failed-test video; bounded private output."""
import os
import sys
# The first operation inside the admitted child is the required /tmp floor check.
_tmp = os.statvfs('/tmp')
_tmp_available = _tmp.f_bavail * _tmp.f_frsize
if _tmp_available - 67108864 < 1073741824:
    raise SystemExit('In-lease /tmp full-allowance reserve check failed; decoder not started.')
import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import threading
import zlib

BASE = Path('/tmp/partydeck-ios-host-name-decode-ui-game-34538972728-v1')
ORIGINAL = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34538972728-ios-engine_ci/ordinary-failure-attachments-v1/kXCTAttachmentScreenRecording_0_BF940F39-DFBE-4F33-8046-7521018A3BC5.mp4')
ORIGINAL_HASH = '2c86f1c16af32595a022327f3e059d8f4e131043406ce941cf28d289b8820e9d'
CONTROL = Path('/root/projects/PartyDeck/artifacts/evidence-storage/shm-evidence-arena-20260910')
CAP = 67108864
FRAME_CAP = 56 * 1024**2
LOG_CAP = 2 * 1024**2
PER_FRAME_CAP = 16 * 1024**2
SELECT = 'if(lt(t,14),isnan(prev_selected_t)+gte(t-prev_selected_t,1),if(lte(t,22),1,gte(t-prev_selected_t,0.2)))+eq(n,258)'
ARGV = ['ffmpeg','-hide_banner','-nostdin','-nostats','-loglevel','info','-copyts','-noautorotate','-threads','1','-i',str(ORIGINAL),'-map','0:v:0','-an','-sn','-dn','-filter_threads','1','-vf',"showinfo@source=checksum=0,select='"+SELECT+"',showinfo@retained=checksum=0",'-fps_mode','passthrough','-c:v','png','-threads','1','-pix_fmt','rgb24','-compression_level','6','-f','image2pipe','pipe:1']

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def allocated():
    return sum(p.lstat().st_blocks * 512 for p in [BASE,*BASE.rglob('*')])

def write_new(path, data):
    # Reserve 1 MiB beyond every write for manifests, logs and block overhead.
    if allocated() + ((len(data)+4095)//4096)*4096 > CAP - 1024**2:
        raise RuntimeError('Declared 64 MiB total derivative allocation would be exceeded.')
    fs = os.statvfs('/tmp')
    remaining = max(0, CAP - allocated())
    if fs.f_bavail * fs.f_frsize - remaining < 1073741824:
        raise RuntimeError('In-lease /tmp remaining-allowance reserve check failed.')
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def write_json(name, value):
    write_new(BASE/name, (json.dumps(value,indent=2)+'\n').encode())

active = json.loads((CONTROL/'active-lease.json').read_text())
assert active['owner'] == 'engine_ci'
assert active['status'] in ('admitted','active')
assert active['planned_peak_additional_bytes'] == CAP
assert active['extra_memory_reserve_bytes'] == 268435456
assert active['pid'] == os.getppid(), 'Child must be directly inside the admitted CLI lease.'
assert ORIGINAL.stat().st_size == 3255255 and sha(ORIGINAL) == ORIGINAL_HASH
assert not (BASE/'decode-start.json').exists(), 'Refuse a second decode.'
start = {'actor':'ui_game','registration_owner':'engine_ci','started_utc':utc(),'lease':active,'tmp_available_bytes_at_entry':_tmp_available,'tmp_available_minus_full_allowance_bytes':_tmp_available-CAP,'tmp_required_floor_bytes':1073741824,'original':{'path':str(ORIGINAL),'bytes':3255255,'sha256':ORIGINAL_HASH},'argv':ARGV,'selection':SELECT,'selection_scope':'Media-time sampling only; no XCTest-to-media clock mapping is established. Sparse first observed frames at least 1 media second apart before 14 s; all decoded source frames in media [14,22] s; first observed frames at least 0.2 media second apart after 22 s; source n=258 included explicitly as metadata-predicted final frame.','limits':{'declared_output_bytes':CAP,'png_payload_bytes':FRAME_CAP,'stderr_bytes':LOG_CAP,'per_png_bytes':PER_FRAME_CAP,'extra_memory_reserve_bytes':268435456},'resolution':'Unscaled 1206x2622; original yuv420p decoded and converted to rgb24 PNG by ffmpeg. No original copy or app capture.','script_sha256':sha(Path(__file__))}
write_json('decode-start.json',start)
frames_dir = BASE/'frames'
frames_dir.mkdir()
stderr = bytearray()
stderr_errors = []
proc = subprocess.Popen(ARGV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def collect_stderr():
    try:
        while True:
            block = proc.stderr.read(8192)
            if not block:
                break
            if len(stderr) + len(block) > LOG_CAP:
                stderr_errors.append('ffmpeg stderr hard cap exceeded')
                proc.terminate()
                break
            stderr.extend(block)
    except BaseException as error:
        stderr_errors.append(repr(error))
        proc.terminate()

thread = threading.Thread(target=collect_stderr,daemon=True)
thread.start()

def exact(size):
    result = bytearray()
    while len(result) < size:
        block = proc.stdout.read(size-len(result))
        if not block:
            raise EOFError('Unexpected EOF in PNG stream')
        result.extend(block)
    return bytes(result)

frames = []
payload_bytes = 0
error = None
try:
    while True:
        first = proc.stdout.read(1)
        if not first:
            break
        signature = first + exact(7)
        assert signature == b'\x89PNG\r\n\x1a\n'
        png = bytearray(signature)
        dimensions = None
        chunks = []
        while True:
            header = exact(8)
            size,kind = struct.unpack('>I4s',header)
            if len(png) + size + 12 > PER_FRAME_CAP:
                raise RuntimeError('Per-PNG hard memory/output cap exceeded')
            data_crc = exact(size+4)
            data,crc = data_crc[:-4],struct.unpack('>I',data_crc[-4:])[0]
            assert (zlib.crc32(kind+data) & 0xffffffff) == crc
            png.extend(header)
            png.extend(data_crc)
            chunks.append(kind.decode('ascii'))
            if kind == b'IHDR':
                dimensions = struct.unpack('>IIBBBBB',data)
                assert dimensions[:2] == (1206,2622)
                assert dimensions[2:4] == (8,2), 'Expected 8-bit RGB PNG'
            if kind == b'IEND':
                assert size == 0
                break
        if payload_bytes + len(png) > FRAME_CAP:
            raise RuntimeError('Total PNG payload hard cap exceeded; partials retained, no second decode')
        ordinal = len(frames)
        target = frames_dir/('retained-%03d.png' % ordinal)
        write_new(target,png)
        payload_bytes += len(png)
        frames.append({'retained_ordinal_zero_based':ordinal,'path':str(target),'bytes':len(png),'sha256':hashlib.sha256(png).hexdigest(),'width':1206,'height':2622,'png_chunks':chunks})
except BaseException as caught:
    error = repr(caught)
    proc.terminate()
finally:
    try:
        returncode = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        returncode = proc.wait()
    thread.join(timeout=15)
    if thread.is_alive():
        stderr_errors.append('stderr collector failed to finish')
    write_new(BASE/'decode-ffmpeg.stderr.txt',bytes(stderr))

text = stderr.decode('utf-8',errors='replace')
pattern = re.compile(r'\[showinfo@(source|retained) @ [^\]]+\]\s+n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([^\s]+)\s+pos:\s*(-?\d+).*?fmt:([^\s]+).*?s:(\d+)x(\d+)')
source_frames=[]
retained=[]
for line in text.splitlines():
    match=pattern.search(line)
    if match:
        value={'index':int(match[2]),'pts':int(match[3]),'pts_time_printed':match[4],'packet_position':int(match[5]),'decoded_format':match[6],'width':int(match[7]),'height':int(match[8])}
        (source_frames if match[1]=='source' else retained).append(value)
config = re.findall(r'\[showinfo@source @ [^\]]+\] config in time_base: ([^,]+), frame_rate: ([^\n]+)',text)
validation_errors=[]
if error: validation_errors.append(error)
validation_errors.extend(stderr_errors)
if returncode != 0: validation_errors.append('ffmpeg return code '+str(returncode))
if config != [('1/600','600/1')]: validation_errors.append('Unexpected or missing source time base: '+repr(config))
if len(source_frames) != 259: validation_errors.append('Unexpected source frame count '+str(len(source_frames)))
if [x['index'] for x in source_frames] != list(range(len(source_frames))): validation_errors.append('Noncontiguous original source indices')
if len(retained) != len(frames): validation_errors.append('Retained PNG/log count mismatch')
position=0
for image,item in zip(frames,retained):
    while position < len(source_frames) and (source_frames[position]['pts'],source_frames[position]['packet_position']) != (item['pts'],item['packet_position']):
        position += 1
    if position >= len(source_frames):
        validation_errors.append('Unable to map retained frame '+str(item['index']))
        break
    original=source_frames[position]
    image.update({'original_decoded_frame_index_zero_based':original['index'],'original_pts':original['pts'],'time_base':'1/600','media_time_exact':str(original['pts'])+'/600','media_time_seconds':original['pts']/600,'showinfo_pts_time_printed':original['pts_time_printed'],'packet_position':original['packet_position']})
    position += 1
if any('original_pts' not in f for f in frames): validation_errors.append('Some PNGs lack original frame binding')
if source_frames and frames:
    expected_dense={x['index'] for x in source_frames if 14*600 <= x['pts'] <= 22*600}
    actual={x.get('original_decoded_frame_index_zero_based') for x in frames}
    if not expected_dense.issubset(actual): validation_errors.append('Dense sampling window incomplete')
    if source_frames[-1]['index'] not in actual: validation_errors.append('Final source frame not retained')
write_json('source-decoded-frame-index.json',{'time_base':'1/600','frame_index_kind':'Zero-based n from source showinfo before select; packet order is not treated as decoded frame order.','frames':source_frames})
manifest={'schema_version':1,'actor':'ui_game','lease_id':active['lease_id'],'original':start['original'],'test_case':'PartyDeckUITests/testSharedControllerHostsANativeTableAndShowsItsInvitation()','source_run_id':34538972728,'source_head':'dd6df8a530d71b51ae4c3b0f4a05246f2e58402f','clock_scope':'All image times are original media PTS/time_base. No authoritative PTS-to-UTC/XCTest anchor has been established.','source_frame_count':len(source_frames),'retained_count':len(frames),'png_payload_bytes':payload_bytes,'selection':SELECT,'frames':frames,'validation_errors':validation_errors}
write_json('frame-manifest.json',manifest)
end={'actor':'ui_game','registration_owner':'engine_ci','lease_id':active['lease_id'],'finished_utc':utc(),'ffmpeg_returncode':returncode,'decode_invocations':1,'source_frame_count':len(source_frames),'retained_png_count':len(frames),'png_payload_bytes':payload_bytes,'directory_allocated_bytes_before_this_receipt':allocated(),'original_sha256_after':sha(ORIGINAL),'validation_errors':validation_errors,'status':'complete' if not validation_errors else 'incomplete_preserved_partials','active_lease_at_completion':json.loads((CONTROL/'active-lease.json').read_text())}
write_json('decode-execution.json',end)
print(json.dumps({'status':end['status'],'source_frame_count':len(source_frames),'retained_png_count':len(frames),'png_payload_bytes':payload_bytes,'manifest':str(BASE/'frame-manifest.json'),'errors':validation_errors},indent=2),flush=True)
raise SystemExit(0 if not validation_errors else 1)
