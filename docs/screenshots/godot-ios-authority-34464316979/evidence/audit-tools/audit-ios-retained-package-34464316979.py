"""Correlate retained CI inputs and package using completed producer audit; no native execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import tarfile
BASE = Path('/tmp/partydeck-engine-ci/34464316979')
HEAD = 'ea84bf49e799675c181545cc3511460b11e0e23d'
SOURCE = BASE / 'source-ea84bf4'
HOST = SOURCE / 'godot/ios-host'
RETAINED = BASE / 'godot-ios-retained-host-test-attempt-1'
PRESERVED = BASE / 'retained-preserved'
ENGINE = BASE / 'godot-ios-host-engine'
FRAMEWORK = BASE / 'godot-ios-host-framework'
RENDERER = BASE / 'godot-ios-host-renderer'
checks = []
def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def file_receipt(path): return {'sha256': digest(path), 'bytes': path.stat().st_size}
def record(path): return {'path': str(path), **file_receipt(path)}
def sha(data): return hashlib.sha256(data).hexdigest()
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label

def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')


result=read(RETAINED/'retained-host-test/evidence/result.json')
resources=read(PRESERVED/'evidence/host-resources.json')
package_checks=[]
def package_check(label, condition):
    package_checks.append({'check':label,'passed':bool(condition)})
    assert condition,label
archive=RETAINED / 'retained-host-test/artifacts/RetainedHost-simulator.app.tar.gz'
with tarfile.open(archive,'r:gz') as package:
    members={m.name:package.extractfile(m).read() for m in package.getmembers() if m.isfile()}
files=[{'member':name,'bytes':len(data),'sha256':sha(data)} for name,data in members.items()]
exe=members['RetainedHost.app/RetainedHost']
package_check('linked executable hash equals original result',sha(exe)==result['executable_sha256'])
magic,cpu,subtype,filetype,commands,command_bytes,flags,reserved=struct.unpack_from('<IiiIIIII',exe)
package_check('64-bit ARM64 executable header',magic==0xfeedfacf and cpu==0x100000c and filetype==2)
offset=32
uuid=None
versions=[]
symtab=None
for _ in range(commands):
    cmd,size=struct.unpack_from('<II',exe,offset)
    assert size>=8 and offset+size<=len(exe)
    if cmd==0x1b: uuid=exe[offset+8:offset+24].hex()
    if cmd==0x32:
        platform,minos,sdk=struct.unpack_from('<III',exe,offset+8)
        versions.append({'platform':platform,'minos':minos,'sdk':sdk})
    if cmd==0x2: symtab=struct.unpack_from('<IIII',exe,offset+8)
    offset+=size
package_check('Mach-O UUID and iOS Simulator SDK load command',uuid and any(v['platform']==7 and v['sdk']==0x1a0400 for v in versions))
package_check('complete load command boundary',offset==32+command_bytes)
expected_symbols=['_main','_OBJC_CLASS_$_PDGodotEngineOwner','_OBJC_CLASS_$_PDGodotPresentation','_OBJC_CLASS_$_PDGBIosQualificationFactory','_OBJC_CLASS_$_PDGBIosQualificationAuthority']
assert symtab
symoff,nsyms,stroff,strsize=symtab
assert symoff+16*nsyms<=len(exe) and stroff+strsize<=len(exe)
strings=exe[stroff:stroff+strsize]
matched_symbols=[]
debug_symbols=[]
for index in range(nsyms):
    strx,ntype,nsect,desc,value=struct.unpack_from('<IBBHQ',exe,symoff+index*16)
    assert strx<strsize
    stop=strings.find(b'\0',strx)
    name=strings[strx:stop].decode(errors='replace')
    if name in expected_symbols:
        item={'name':name,'type':ntype,'section':nsect,'value':value}
        (debug_symbols if ntype & 0xe0 else matched_symbols).append(item)
package_check('all five required native/Kotlin owner symbols are defined in linked executable',len(matched_symbols)==len(expected_symbols) and {s['name'] for s in matched_symbols}==set(expected_symbols) and all(s['type']&0x0e==0x0e and s['section']>0 and s['value']>0 for s in matched_symbols))
symbols_log=(RETAINED / 'retained-host-test/evidence/symbols.log').read_text()
package_check('required symbols also present in original nm output',all(re.search(r'(?m)^.*\s'+re.escape(name)+r'$',symbols_log) for name in expected_symbols))
plist=plistlib.loads(members['RetainedHost.app/Info.plist'])
package_check('Simulator bundle and Xcode build identity',plist['CFBundleSupportedPlatforms']==['iPhoneSimulator'] and plist['DTXcodeBuild']=='17E202' and plist['CFBundleExecutable']=='RetainedHost')
pack=members['RetainedHost.app/ProbeResources/partydeck-last-light.pck']
package_check('bundled PCK matches audited producer and staged resource',sha(pack)==digest(RENDERER/'partydeck-last-light.pck')==resources['optional_shared_pack']['sha256'] and len(pack)==resources['optional_shared_pack']['bytes'])
package_check('bundled companion receipt equals exact producer bytes',sha(members['RetainedHost.app/ProbeResources/partydeck-last-light.receipt.json'])==digest(RENDERER/'partydeck-last-light.receipt.json'))
package_check('bundled fixture and manifest',sha(members['RetainedHost.app/ProbeResources/Launch.json'])==resources['fixture_sha256'] and sha(members['RetainedHost.app/ProbeResources/fixture-manifest.json'])==resources['fixture_manifest_sha256'])
for name,expected in resources['license_bundle_sha256'].items(): package_check('bundled license '+name,sha(members['RetainedHost.app/ProbeResources/Licenses/'+name])==expected)
package_summary={'runId':34464316979,'headSha':HEAD,'scope':'Linked app package and static symbol identity only. No app was executed during this audit.','archive':record(archive),'fileCount':len(files),'files':files,'executable':{'bytes':len(exe),'sha256':sha(exe),'machOUuid':uuid,'cpuType':cpu,'fileType':filetype,'buildVersions':versions,'symbolTableEntries':nsyms,'requiredDefinedSymbols':matched_symbols,'matchingDebugRecordsExcludedFromDefinitionCheck':debug_symbols},'plist':plist,'packSha256':sha(pack),'inputAudit':record(BASE/'retained-input-evidence-summary.json'),'originalSymbolLog':record(RETAINED/'retained-host-test/evidence/symbols.log'),'checks':package_checks,'binaryFormatReferences':record(BASE/'research/macho/references.json'),'initialAuditCorrection':record(BASE/'retained-package-initial-audit-correction.json')}
write_new(BASE/'retained-package-evidence-summary.json',package_summary)
print(json.dumps({'packageAudit':record(BASE/'retained-package-evidence-summary.json'),'checksPassed':len(package_checks),'executableSha256':sha(exe)}),flush=True)
