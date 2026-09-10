from pathlib import Path
from hashlib import sha256
import json,zipfile,re,struct,subprocess

OUT=Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
COLLECTION=json.loads((OUT/'last-run-status.json').read_text())
PACKAGES=OUT/'android-packages-and-shrinker-reports'
REPORTS=OUT/'android-jvm-reports'
NATIVE=REPORTS/'build/ci/android'
TOOLS=Path('/opt/android-sdk/build-tools/36.0.0')
DERIVED=OUT/'review/package-tools'; DERIVED.mkdir(parents=True,exist_ok=False)
SOURCE_AUDIT=json.loads((OUT/'review/source-inputs-audit.json').read_text())
assert SOURCE_AUDIT['run_id']==34503251315 and SOURCE_AUDIT['source_revision']==COLLECTION['head_sha']
PCK=SOURCE_AUDIT['expected_pack_sha256']


def file_hash(path):
    result=sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024): result.update(block)
    return result.hexdigest()

def identity(path): return {'path':str(path),'bytes':path.stat().st_size,'sha256':file_hash(path)}

def run(label,args,expected_success=True):
    result=subprocess.run([str(a) for a in args],capture_output=True,timeout=90)
    stdout=DERIVED/(label+'.stdout'); stderr=DERIVED/(label+'.stderr')
    stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
    assert (result.returncode==0)==expected_success,(label,result.returncode)
    return {'command':[str(a) for a in args],'exit_code':result.returncode,'stdout':identity(stdout),'stderr':identity(stderr)}

def dump_tree(text):
    root=None; stack=[]
    for line in text.splitlines():
        m=re.match(r'^(\s*)E: ([^ ]+)',line)
        if m:
            indent=len(m[1]); node={'tag':m[2],'attrs':{},'children':[]}
            while stack and stack[-1][0]>=indent: stack.pop()
            if stack: stack[-1][1]['children'].append(node)
            else: assert root is None; root=node
            stack.append((indent,node)); continue
        m=re.match(r'^\s*A: ([^=]+)=(.*)$',line)
        if m:
            key=m[1].split(':')[-1].split('(')[0]; value=m[2]
            if value.startswith('"'): value=json.JSONDecoder().raw_decode(value)[0]
            stack[-1][1]['attrs'][key]=value
    return root

signing=json.loads((NATIVE/'packages/runtime-package.json').read_text())
smokes={name:json.loads((NATIVE/name/'smoke-result.json').read_text()) for name in ['debug','optimized-test-signed']}
paths={
 'debug':PACKAGES/'androidApp/build/outputs/apk/debug/androidApp-debug.apk',
 'unsigned-release':PACKAGES/'androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk',
 'optimized-test-signed':PACKAGES/'build/ci/android/packages/PartyDeck-release-ci-test-signed.apk',
 'release-bundle':PACKAGES/'androidApp/build/outputs/bundle/release/androidApp-release.aab',
}
expected={'debug':smokes['debug']['apk_sha256'],'unsigned-release':signing['originalUnsignedSha256'],'optimized-test-signed':signing['runtimeApkSha256']}
assert smokes['optimized-test-signed']['apk_sha256']==expected['optimized-test-signed']
assert signing['distributionSigned'] is False and signing['signingIdentity']=='disposable-ci-test-key'
build=(Path('/root/projects/PartyDeck/artifacts/evidence-storage/source-1cd34a3/source-1cd34a3/androidApp/build.gradle.kts')).read_text()
assert 'isMinifyEnabled = true' in build and 'isShrinkResources = true' in build
records={}; payloads={}
for name,path in paths.items():
    before=path.stat(); record={'artifact':identity(path),'commands':{}}
    if name in expected: assert record['artifact']['sha256']==expected[name],name
    prefix='base/' if name=='release-bundle' else ''
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist(); assert len(names)==len(set(names))
        candidates=[n for n in names if n.lower().endswith('.pck')]
        assert candidates==[prefix+'assets/partydeck-last-light.pck'],(name,candidates)
        entry=archive.getinfo(candidates[0]); data=archive.read(entry)
        assert sha256(data).hexdigest()==PCK and len(data)==SOURCE_AUDIT['expected_pack_bytes']
        if name!='release-bundle': assert entry.compress_type==zipfile.ZIP_STORED
        record['pck']={'path':entry.filename,'sha256':sha256(data).hexdigest(),'bytes':len(data),'compression':entry.compress_type,'count':1}
        dex=[]
        for info in archive.infolist():
            if info.filename.endswith('.dex'):
                data=archive.read(info); assert data[:4]==b'dex\n' and struct.unpack_from('<I',data,32)[0]==len(data)
                dex.append({'path':info.filename,'bytes':len(data),'sha256':sha256(data).hexdigest(),'class_definition_count':struct.unpack_from('<I',data,96)[0]})
        record['dex']=dex; record['dex_class_definition_count']=sum(d['class_definition_count'] for d in dex)
        if name in ['unsigned-release','optimized-test-signed']:
            inventory={}
            for info in archive.infolist():
                if info.is_dir(): continue
                h=sha256()
                with archive.open(info) as stream:
                    while chunk:=stream.read(1024*1024): h.update(chunk)
                inventory[info.filename]={'bytes':info.file_size,'sha256':h.hexdigest()}
            payloads[name]=inventory
            p=DERIVED/(name+'-payload-inventory.json'); p.write_text(json.dumps(inventory,indent=2)+'\n')
            record['payload_inventory']=identity(p)
    if name!='release-bundle':
        record['commands']['manifest']=run(name+'-manifest',[TOOLS/'aapt2','dump','xmltree',path,'--file','AndroidManifest.xml'])
        record['commands']['badging']=run(name+'-badging',[TOOLS/'aapt2','dump','badging',path])
        record['commands']['signature']=run(name+'-signature',[TOOLS/'apksigner','verify','--verbose','--print-certs',path],name!='unsigned-release')
        record['commands']['alignment']=run(name+'-alignment',[TOOLS/'zipalign','-c','-P','16','-v','4',path])
        manifest=dump_tree((DERIVED/(name+'-manifest.stdout')).read_text())
        assert manifest['attrs']['package']=='dev.partydeck.app'
        app=next(c for c in manifest['children'] if c['tag']=='application')
        assert app['attrs'].get('debuggable','false')==('true' if name=='debug' else 'false')
        components=[c for c in app['children'] if c['tag'] in ('activity','service','provider','receiver')]
        renderer=next(c['attrs'] for c in components if c['attrs'].get('name')=='dev.partydeck.app.godot.SessionGodotActivity')
        broker=next(c['attrs'] for c in components if c['attrs'].get('name')=='dev.partydeck.app.godot.GodotSessionBrokerService')
        assert renderer['exported']=='false' and renderer['process']==':godot' and renderer['screenOrientation']=='13' and renderer['resizeableActivity']=='true'
        assert broker['exported']=='false' and broker.get('process') is None and app['attrs'].get('process') is None
        record['manifest']={'package':'dev.partydeck.app','debuggable':app['attrs'].get('debuggable','false'),'renderer':renderer,'broker':broker}
        signature=(DERIVED/(name+'-signature.stdout')).read_text()
        certificates=re.findall(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]{64})',signature)
        record['signer_certificate_sha256']=certificates
        if name=='optimized-test-signed': assert certificates==[signing['certificateSha256']]
    after=path.stat(); assert (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino)
    assert file_hash(path)==record['artifact']['sha256']
    record['file_stable_through_inspection']=True; records[name]=record
    print(json.dumps({'artifact':name,'sha256':record['artifact']['sha256'],'pck_sha256':PCK,'class_definitions':record['dex_class_definition_count']}),flush=True)

original=payloads['unsigned-release']; runtime=payloads['optimized-test-signed']
extra=set(runtime)-set(original); missing=set(original)-set(runtime)
assert not missing
assert all(re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))',p,re.I) for p in extra),extra
assert all(runtime[p]==original[p] for p in original),'Runtime signing changed an application payload'
assert records['unsigned-release']['dex']==records['optimized-test-signed']['dex']
assert records['optimized-test-signed']['dex_class_definition_count']<records['debug']['dex_class_definition_count']
summary={'result':'pass','run_id':34503251315,'commit':COLLECTION['head_sha'],'packages':records,'runtime_signing_receipt':identity(NATIVE/'packages/runtime-package.json'),'optimized_runtime_all_unsigned_payload_bytes_unchanged':True,'compared_unsigned_payload_count':len(original),'runtime_extra_signature_entries':sorted(extra),'optimized_apk_is_not_debuggable':True,'disposable_test_signing_certificate_matches_receipt':True,'distribution_signed':False,'ordinary_smoke_receipt_apk_hashes_match_actual_archives':True,'same_expected_pck_in_all_four_archives':True,'execution_scope':'Read-only package inspection; no app or Godot execution by reviewer.'}
summary['audit_script']=identity(Path(__file__))
summary['exact_source_inputs_audit']=identity(OUT/'review/source-inputs-audit.json')
p=OUT/'review/package-audit.json'
with p.open('x') as stream: stream.write(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'receipt':str(p),'sha256':file_hash(p),'optimized_payloads_match_unsigned':len(original),'extra_signature_entries':sorted(extra),'native_apk_hashes_verified':True},indent=2),flush=True)
