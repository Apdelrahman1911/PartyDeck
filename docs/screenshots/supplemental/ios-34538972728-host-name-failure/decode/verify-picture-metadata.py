#!/usr/bin/env python3
"""Verify original packet-to-picture metadata; never decode video or export pixels."""
from pathlib import Path
import hashlib
import json
import re

BASE=Path(__file__).resolve().parent
HEADERS=json.loads((BASE/'h264-picture-headers.json').read_text())
PROBES=json.loads((BASE/'probe-receipts.json').read_text())
VIDEO=Path(PROBES['original']['path']).read_bytes()
assert hashlib.sha256(VIDEO).hexdigest()==PROBES['original']['sha256']

class Bits:
    def __init__(self,data):
        self.data=data.replace(b'\x00\x00\x03',b'\x00\x00')
        self.pos=0
    def u(self,n):
        result=0
        for _ in range(n):
            result=(result<<1)|((self.data[self.pos//8]>>(7-self.pos%8))&1)
            self.pos+=1
        return result
    def ue(self):
        n=0
        while not self.u(1):
            n+=1
            assert n<32
        return (1<<n)-1+self.u(n)
    def se(self):
        x=self.ue()
        return ((x+1)//2)*(1 if x%2 else -1)

SPS={}
PPS={}
def parse_sps(nal):
    r=Bits(nal[1:])
    profile=r.u(8)
    r.u(8)
    level=r.u(8)
    sid=r.ue()
    chroma,sep=1,0
    if profile in [100,110,122,244,44,83,86,118,128,138,139,134,135]:
        chroma=r.ue()
        if chroma==3:
            sep=r.u(1)
        r.ue()
        r.ue()
        r.u(1)
        if r.u(1):
            for i in range(8 if chroma!=3 else 12):
                if r.u(1):
                    last=next_scale=8
                    for _ in range(16 if i<6 else 64):
                        if next_scale:
                            next_scale=(last+r.se()+256)%256
                        last=next_scale or last
    framebits=r.ue()+4
    poctype=r.ue()
    assert poctype==0
    pocbits=r.ue()+4
    refs=r.ue()
    gaps=r.u(1)
    r.ue()
    r.ue()
    frameonly=r.u(1)
    item={'sps_id':sid,'profile':profile,'level':level,'chroma':chroma,
          'separate_colour_plane_flag':sep,'frame_num_bits':framebits,
          'poc_type':poctype,'poc_lsb_bits':pocbits,'max_refs':refs,
          'gaps_flag':gaps,'frame_mbs_only_flag':frameonly}
    SPS[sid]=item

def parse_pps(nal):
    r=Bits(nal[1:])
    pid,sid=r.ue(),r.ue()
    entropy,bottom=r.u(1),r.u(1)
    PPS[pid]={'pps_id':pid,'sps_id':sid,'entropy_coding_mode_flag':entropy,
              'bottom_field_pic_order_in_frame_present_flag':bottom}

start=VIDEO.find(b'avcC')
assert start>=4 and VIDEO.find(b'avcC',start+4)<0
size=int.from_bytes(VIDEO[start-4:start],'big')
avcc=VIDEO[start+4:start-4+size]
assert avcc.hex()==HEADERS['avcc_hex']
length_size=(avcc[4]&3)+1
position=6
for _ in range(avcc[5]&31):
    size=int.from_bytes(avcc[position:position+2],'big')
    position+=2
    parse_sps(avcc[position:position+size])
    position+=size
count=avcc[position]
position+=1
for _ in range(count):
    size=int.from_bytes(avcc[position:position+2],'big')
    position+=2
    parse_pps(avcc[position:position+size])
    position+=size

packets=json.loads((BASE/'video-packets.json').read_text())['packets']
parsed=[]
for index,packet in enumerate(packets):
    start,size=int(packet['pos']),int(packet['size'])
    data=VIDEO[start:start+size]
    position=0
    slices=[]
    nal_types=[]
    while position<len(data):
        size=int.from_bytes(data[position:position+length_size],'big')
        position+=length_size
        nal=data[position:position+size]
        position+=size
        assert size>0 and len(nal)==size and (nal[0]&0x80)==0
        kind=nal[0]&31
        nal_types.append(kind)
        if kind==7:
            parse_sps(nal)
        if kind==8:
            parse_pps(nal)
        if kind not in (1,5):
            continue
        r=Bits(nal[1:])
        first,slice_type,pid=r.ue(),r.ue()%5,r.ue()
        pp=PPS[pid]
        sp=SPS[pp['sps_id']]
        if sp['separate_colour_plane_flag']:
            r.u(2)
        frame=r.u(sp['frame_num_bits'])
        assert sp['frame_mbs_only_flag']==1
        idr=r.ue() if kind==5 else None
        poc=r.u(sp['poc_lsb_bits'])
        bottom=r.se() if pp['bottom_field_pic_order_in_frame_present_flag'] else 0
        slices.append({'nal_unit_type':kind,'nal_ref_idc':nal[0]>>5,
                       'first_mb_in_slice':first,'slice_type':slice_type,'pps_id':pid,
                       'frame_num':frame,'idr_pic_id':idr,'poc_lsb':poc,
                       'poc_lsb_bits':sp['poc_lsb_bits'],'bottom_delta':bottom})
    assert position==len(data) and len(slices)==1
    row={'packet_demux_index':index,'packet_pts':int(packet['pts']),
         'packet_dts':int(packet['dts']),'packet_position':start,'packet_size':len(data),
         'packet_sha256':hashlib.sha256(data).hexdigest(),'nal_unit_types':nal_types,
         'slice_count':len(slices),'picture':slices[0]}
    assert row==HEADERS['packets'][index],index
    parsed.append(row)
assert {str(k):v for k,v in SPS.items()}==HEADERS['sps']
assert {str(k):v for k,v in PPS.items()}==HEADERS['pps']

epochs=[]
for row in parsed:
    if row['picture']['nal_unit_type']==5:
        epochs.append([])
    epochs[-1].append(row)
ordered=[]
for epoch in epochs:
    epoch.sort(key=lambda row:row['picture']['poc_lsb'])
    assert [row['picture']['poc_lsb'] for row in epoch]==list(range(len(epoch)))
    assert len(epoch)<=29 and all(row['picture']['poc_lsb_bits']==6 for row in epoch)
    ordered.extend(epoch)

log=(BASE/'decode-ffmpeg.stderr.txt').read_text()
source=[]
retained=[]
for line in log.splitlines():
    match=re.search(r'\[showinfo@(source|retained) @ [^\]]+\]\s+n:\s*(\d+)\s+pts:\s*(-?\d+).*iskey:(\d+) type:(\w+)',line)
    if match:
        row={'n':int(match[2]),'pts':int(match[3]),'iskey':int(match[4]),'type':match[5]}
        if match[1]=='source':
            source.append(row)
        else:
            assert row['pts']==source[-1]['pts']
            row['source_n']=source[-1]['n']
            retained.append(row)
assert len(source)==len(ordered)==259
binding=json.loads((BASE/'original-packet-frame-binding.json').read_text())['mappings']
for n,(decoder,packet,row) in enumerate(zip(source,ordered,binding)):
    assert decoder['n']==n
    assert decoder['type']=={0:'P',1:'B',2:'I',3:'SP',4:'SI'}[packet['picture']['slice_type']]
    assert decoder['iskey']==int(packet['picture']['nal_unit_type']==5)
    assert row['decoded_source_frame_index']==n
    assert row['original_packet_pts']==packet['packet_pts']
    assert row['packet_demux_index']==packet['packet_demux_index']
    assert row['packet_sha256']==packet['packet_sha256']

expected=[]
previous=None
for decoder in source:
    t=decoder['pts']/600
    chosen=((previous is None or t-previous>=1) if t<14 else (True if t<=22 else t-previous>=0.2))
    if chosen or decoder['n']==258:
        expected.append(decoder['n'])
        previous=t
assert expected==[r['source_n'] for r in retained]
manifest=json.loads((BASE/'frame-manifest-v3.json').read_text())
assert len(manifest['frames'])==len(retained)==84
for item,decoder in zip(manifest['frames'],retained):
    assert item['original_decoded_frame_index_zero_based']==decoder['source_n']
    assert item['decoded_source_showinfo_pts']==decoder['pts']
    assert item['original_packet_pts']==binding[decoder['source_n']]['original_packet_pts']
    p=Path(item['path'])
    assert p.stat().st_size==item['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
result={'status':'verified','video_decodes_in_this_verifier':0,'original_sha256':hashlib.sha256(VIDEO).hexdigest(),
        'packet_headers_reparsed':len(parsed),'idr_epochs':len(epochs),'decoded_frames_bound':len(binding),
        'retained_pngs_rehashed':len(retained),'selection_matches_original_filter_expression':True,
        'all_original_packet_types_and_keyflags_match_decoded_frames':True,
        'png_payload_bytes':sum(f['bytes'] for f in manifest['frames']),
        'metadata_verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (BASE/'packet-header-verification.json').open('x') as stream:
    json.dump(result,stream,indent=2)
    stream.write('\n')
print(json.dumps(result,indent=2))
