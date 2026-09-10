"""Preserve and independently verify recorded desktop originals, without execution."""
import ast,hashlib,json,textwrap
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path('/root/projects/PartyDeck/artifacts/evidence-storage/three-d-demand-redraw-20260910')
OUT=Path('/tmp/partydeck-gallery-next-demand-source-audit.json')
assert not OUT.exists()
tree=ast.parse(Path('/tmp/partydeck-gallery-1717-audit-android.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'read','sha','original','verify','png'}],type_ignores=[]),'<read-only helpers>','exec'))
TABLE='45ee2ac81cd371f13b16e2b29b47468cbd86f2cbe98c1a0f8ba55787609cdf40'
assert sha(R/'png-manifest.json')=='eb1db6b714bd9d31c44e8c26be2eb1d7bdabc41d8be5c4e8609c8a473b33e837'
assert sha(R/'verification-receipt.json')=='3fc0d76c7a6df5cb552b9be38505ed0f8b05a2a9fe4ed940e29cbf73b6b88437'
manifest=read(R/'png-manifest.json'); receipt=read(R/'verification-receipt.json'); handoff=read(R/'handoff.json')
assert manifest['tableSha256']==TABLE and len(manifest['originals'])==13
for key in ['changedFilesManifest','integrationPatch','tableOnlyPatch','independentReview','executionReceipt']:
 record=handoff[key];assert sha(record['path'])==record['sha256']
sums_count=0
for line in (R/'SHA256SUMS').read_text().splitlines():
 digest,relative=line.split('  ',1)
 path=R/relative
 assert path.is_file() and path.resolve().is_relative_to(R.resolve())
 assert sha(path)==digest,path
 sums_count+=1
inputs=read(R/'validation-final/input-manifest.json')
for record in inputs['files']:
 verify({'path':str(R/'validation-final'/record['relativePath']),'bytes':record['bytes'],'sha256':record['sha256']})
assert len(inputs['files'])==receipt['sourceInputsVerified']==155
changes=read(R/'freeze-01/changed-files.json')
for record in changes['files']:
 for p in [R/'freeze-01/proposed'/record['relativePath'],R/'validation-final/source'/record['relativePath']]:
  verify({'path':str(p),'bytes':record['bytes'],'sha256':record['sha256']})
 if 'baseSha256' in record:assert sha(R/'freeze-01/base'/record['relativePath'])==record['baseSha256']
upstream=read(R/'upstream-source-provenance.json')
for record in upstream:
 verify({'path':str(R/'upstream'/record['relativePath']),'bytes':record['bytes'],'sha256':record['sha256']})
 assert record['engineCommit']=='ed1daf0bf001b61586d9930840f2f1394092c079'
captures=[];cases=[]
for name in ['redraw','native-bridge','terminal-return','3d-scene-portrait','3d-scene-large-text']:
 rec=read(R/'validation-final'/(name+'-receipt.json'))
 report_path=R/'validation-final'/name/'report.json';report=read(report_path)
 expected=receipt['reports'][name]
 assert rec['exitCode']==expected['exitCode']==0
 assert report['result']==expected['result']=='passed'
 assert sha(report_path)==expected['reportSha256']
 assert sha(R/'validation-final'/(name+'.log'))==expected['logSha256']
 assert rec['tableSha256']==TABLE
 assert sha(rec['command'][5])==rec['engineSha256']
 if report.get('checks'):
  assert len(report['checks'])==expected['assertions'] and all(x['passed'] for x in report['checks'])
  assert rec['checks']==expected['assertions']
 case_captures=[]
 if name.startswith('3d-scene-'):
  scale=2.0 if name.endswith('large-text') else 1.0
  assert report['width']==390 and report['height']==844 and report['textScale']==scale
  observations={Path(x['capture']).name:x for x in report['observations'] if 'capture' in x}
  originals=[x for x in manifest['originals'] if Path(x['relativePath']).parent.name==name]
  assert set(observations)=={Path(x['relativePath']).name for x in originals}
  for record in originals:
   path=R/record['relativePath']
   verify({'path':str(path),'bytes':record['bytes'],'sha256':record['sha256']})
   diagnostic=path.with_suffix('.json'); metrics=read(diagnostic)
   assert metrics==observations[path.name]['diagnostics']
   assert metrics['viewport']=={'width':390,'height':844}
   if any(part in path.name for part in ['concealed','covered']):
    assert metrics['handConcealed'] and all(metrics[k]==0 for k in ['selectedCount','privateFaceCount','privateLabelCount'])
   expected_selected={'02-revealed-selected.png':2,'02a-selection-limit.png':3,'02b-deselected-last.png':2}
   if path.name in expected_selected:assert metrics['selectedCount']==expected_selected[path.name]
   cap=png(path,relative_path=name+'/'+path.name,original_filename=path.name,scenario=path.stem,
     presentation='3d',font_scale=scale,source_revision=None,source_revision_exact=False,
     source_fingerprint=TABLE,source_fingerprint_kind='frozen three_d/table.gd SHA-256',
     metrics=metrics,metrics_source=str(diagnostic),test_result='passed',
     execution_receipt=str(R/'validation-final'/(name+'-receipt.json')),
     platform='Godot 4.7.2 official, desktop Xvfb/Mesa llvmpipe Compatibility')
   assert (cap['width_px'],cap['height_px'])==(390,844)
   captures.append(cap);case_captures.append(cap)
 cases.append({'name':name,'receipt':original(R/'validation-final'/(name+'-receipt.json')),
  'report':original(report_path),'report_assertions':expected['assertions'],'result':'passed',
  'capture_files':[x['source_original'] for x in case_captures],
  'recorded_scope':report.get('limitations',report.get('scope'))})
assert len(captures)==13
failure=read(R/'iteration-02/redraw/report.json')
failed_checks=[x for x in failure['checks'] if not x['passed']]
assert failure['result']=='failed' and len(failed_checks)==3
assert read(R/'iteration-02/redraw-receipt.json')['exitCode']==1
first_log=(R/'iteration-01/import.log').read_text()
assert '_exit_tree' in first_log and 'Parse Error' in first_log
assert read(R/'iteration-01/import-receipt.json')['exitCode']==0
assert read(R/'iteration-03/redraw/report.json')['result']=='passed'
evidence={}
def add(p,kind='original desktop evidence'):
 p=Path(p); rel=str(p.relative_to(R))
 assert p.suffix!='.png' and p.stat().st_size<10*1024*1024
 evidence[str(p)]=original(p,relative_path=rel,artifact_type=kind)
for name in ['README.md','SHA256SUMS','handoff.json','png-manifest.json','verification-receipt.json','upstream-source-provenance.json']:
 add(R/name)
for p in (R/'freeze-01').rglob('*'):
 if p.is_file():add(p,'frozen candidate source or review')
for phase_name in ['iteration-01','iteration-02','iteration-03','validation-final']:
 base=R/phase_name
 for p in base.rglob('*'):
  if not p.is_file():continue
  relative=p.relative_to(base)
  if relative.parts[0] not in ['source','fixtures'] and p.suffix!='.png':add(p)
 if phase_name!='validation-final':
  for relative in ['source/godot/renderer/presentations/three_d/table.gd','source/godot/renderer/tests/three_d_redraw_check.gd']:
   if (base/relative).is_file():add(base/relative,'original failed/corrected candidate source')
for relative in ['project.godot','scripts/main.gd','scripts/renderer_controller.gd','presentations/three_d/card_3d.gd','presentations/three_d/table.gd','tests/three_d_scene_check.gd','tests/three_d_redraw_check.gd','tests/native_bridge_check.gd','tests/terminal_return_render_check.gd']:
 add(R/'validation-final/source/godot/renderer'/relative,'exact executed desktop source')
for p in (R/'validation-final/fixtures').glob('*.json'):add(p,'exact static fixture')
result={'schema_version':1,'audit_kind':'independent recorded evidence read; no runtime execution',
 'completed_at':datetime.now(timezone.utc).isoformat(),'source_directory':str(R),'source_fingerprint':TABLE,
 'source_revision_exact':False,'verified_source_checksum_entries':sums_count,'final_inputs_verified':len(inputs['files']),
 'pinned_upstream_files_verified':len(upstream),'cases':cases,'captures':captures,'capture_count':13,
 'evidence_files':list(evidence.values()),'preserved_failures':[
  {'iteration':'01','import_command_exit':0,'original_log_reports_parse_failure':True,'failure':'Duplicated _exit_tree function; a zero import process exit is not a clean parse result.'},
  {'iteration':'02','command_exit':1,'original_failed_checks':failed_checks,'zero_size_correction':'The node clamps a zero size to 2 by 2; later checks separately cover renderer skip and zero view count.'}],
 'limits':['Recorded final desktop scene input/privacy fixtures and focused redraw reports passed.','Native timing, device touch, native cover presentation and an iOS stall fix are not established.','The native-bridge report uses Java registry doubles and does not execute Android JNI.','The local captures have a frozen source fingerprint; no exact clean CI revision is asserted.'],
 'audit_script':original(Path(__file__))}
with OUT.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
# Derived review sheets remain outside the gallery.
out=Path('/tmp/partydeck-gallery-next-review-sheets/demand-redraw');out.mkdir(parents=True,exist_ok=False)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14);sheets=[]
for name in ['3d-scene-portrait','3d-scene-large-text']:
 group=[x for x in captures if Path(x['source_original']).parent.name==name]
 for start in range(0,len(group),4):
  page=group[start:start+4];canvas=Image.new('RGB',(len(page)*402+12,930),'#eeeeee');draw=ImageDraw.Draw(canvas)
  for i,c in enumerate(page):
   x=12+i*402;draw.text((x,8),name,font=font,fill='black');draw.text((x,30),c['original_filename'],font=font,fill='black')
   canvas.paste(Image.open(c['source_original']).convert('RGB'),(x,70))
  p=out/(name+'-page-'+str(start//4+1)+'.png');canvas.save(p);sheets.append({'path':str(p),'files':[x['source_original'] for x in page]})
(out/'index.json').write_text(json.dumps(sheets,indent=2)+'\n')
print(json.dumps({'audit':str(OUT),'sha256':sha(OUT),'originals':13,'evidence':len(evidence),'verified_checksum_entries':sums_count,'sheets':len(sheets)}))
