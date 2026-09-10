#!/usr/bin/env python3
"""Bind existing original images and receipts; no image copying, viewing or execution."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json,struct

HANDOFF=Path(__file__).resolve().parents[1]
OWNER=Path('/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq')
AUDIT=Path('/tmp/partydeck-3d-resource-reuse-assets-v1-7j78j2k7')
GAME_REVIEW=Path('/tmp/partydeck-card3d-reuse-review-game-v1')
SECURITY_REVIEW=Path('/tmp/partydeck-3d-resource-reuse-security-candidate-v1')
GALLERY='docs/screenshots/godot-card3d-reuse-desktop-20260910'
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
OWNER_FREEZE_SHA='7c274914ff2f3d8e500458ef5303492e02d2af2144c04e2d16f3659bf8a8b5e3'
owner_freeze=json.loads((OWNER/'freeze.json').read_text())
owner_entries={item['path']:item for item in owner_freeze['files']}
references={}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def reference(path,expected=None):
    path=Path(path)
    data=path.read_bytes()
    checksum=digest(data)
    if expected is not None:
        assert checksum==expected,(str(path),checksum,expected)
    owner_bound=False
    if path.is_relative_to(OWNER) and path!=OWNER/'freeze.json':
        item=owner_entries[path.relative_to(OWNER).as_posix()]
        assert checksum==item['sha256'] and len(data)==item['bytes'],str(path)
        owner_bound=True
    record={'original_path':str(path),'bytes':len(data),'sha256':checksum,'matches_original_owner_freeze':owner_bound}
    references[str(path)]=record
    return dict(record)

source_refs={
    'owner_freeze':reference(OWNER/'freeze.json',OWNER_FREEZE_SHA),
    'owner_source_binding':reference(OWNER/'source-binding.json','b2498436798a2e44ff184ec380ce22c7127576531fe822ab77452293e42f3d4a'),
    'candidate_source_freeze':reference(OWNER/'candidate-source-freeze.json','8f1aa984995a77956c651034233ea45aaeb99f1320b068c428616d3e4199338a'),
    'candidate_patch':reference(OWNER/'card3d-resource-reuse.patch','a904d39cb259cae75085001f4733a0d7ee49cd1f2693f8c723ae914541c9b484'),
    'owner_result':reference(OWNER/'RESULT.md','50ab3ce841661e9fb3ff78eae33cb2f84822474c2328e8e3e60e5b6d24200400'),
    'owner_validation_summary':reference(OWNER/'receipts/validation-summary.json','abcd5171d3536396a051c9748223f9b045625f76a2e16f413d469b50f0dee76f'),
    'original_pixel_comparison':reference(OWNER/'evidence/pixel-comparison.json','52949f7e68018aff80760409f95958825a91e2714fe6703dce2c3cfff37519cd'),
    'engine_version_receipt':reference(OWNER/'receipts/godot-version.json','e15e966f3e6617fc193eda2773b44dfe6ea3c5a2681f841a1191b6bcd85f0516'),
    'fixture_binding':reference(OWNER/'receipts/fixture-binding.json','4ef5b040297bce727147247c656cb569ddf6147e8b40dba353e7eec1f3d91343'),
    'rendering_review':reference(GAME_REVIEW/'REVIEW.md','ddc36c9f95035704c4de0aa1027a7c486b8e076e2424091f1530b9cdd165b90b'),
    'rendering_review_receipt':reference(GAME_REVIEW/'review.json','aba0095eec8bdac9131fc058f36ee0d87371a7ba786a90cf8bdc606445281cff'),
    'rendering_review_freeze':reference(GAME_REVIEW/'FROZEN.json','e00c4432163f26425bc01bd37977de1d88810ee50adfa5af6a14d3462ee9038b'),
    'security_source_review':reference(SECURITY_REVIEW/'SOURCE-REVIEW.md','facf043271ceb3fb6fd0f58dc63dfa2897337108d446c9fc8db7ded7856ae989'),
    'security_source_review_receipt':reference(SECURITY_REVIEW/'review-receipt.json','bcdde5679e40b0319b19f3682e3a7f7e01612d024580b04840402a39e7f45803'),
    'source_audit':reference(AUDIT/'REPORT.md','7d9489e00703a6cd59ba12b26da7ac30519ba96a4eac3a6f1439ee8f33bf07b0'),
    'baseline_pack_source_association':reference(AUDIT/'receipts/redraw-source-binding.json'),
}

viewed={
 'candidate/portrait/02-revealed-selected.png':{
    'sha256':'81ed93be5c09cb651fa182601adaebc6d4df7625623650ab37599bed886d825b',
    'observation':'Five face-up cards have upright rank labels; the first and last cards show selected borders and check marks. The recorded viewport includes Hide hand and Play 2.'},
 'candidate/large-text/02-revealed-selected.png':{
    'sha256':'8f927ca58390aabe677d476d68ec345c2d4cb952935da54131e97165e4303737',
    'observation':'The recorded scrolled view shows the lower card strip, large hand-choice buttons and Play 2. The first and last hand-choice buttons show selected state.'},
}
view_receipt={
    'recorded_utc':NOW,
    'kind':'Attestation of already completed direct owner views; no new viewing in this publication pass.',
    'viewer':'/root/assets',
    'viewer_role':'source candidate owner',
    'view_method':'Existing functions.exec calls to tools.view_image during the completed candidate-validation turn; image items 0 and 1.',
    'exact_view_timestamp_utc':None,
    'timestamp_limit':'The prior tool view did not produce a separately retained wall-clock timestamp. The existing owner RESULT.md records these two selected-capture views before the owner freeze.',
    'prior_owner_attestation':source_refs['owner_result'],
    'views':[{'original_path':str(OWNER/'evidence'/relative),'sha256':item['sha256'],'observation':item['observation']} for relative,item in viewed.items()],
    'not_viewed':'No baseline original and no other candidate original was directly viewed by assets in this validation/publication sequence. Same-byte counterparts may reference an observation while remaining actually_viewed=false.',
    'independent_review_limit':'review_game independently hashed and byte-compared the 20 pairs; its report explicitly records no image viewing.'
}
view_path=HANDOFF/'receipts/owner-direct-views.json'
view_path.write_text(json.dumps(view_receipt,indent=2)+'\n')
view_ref={'path':str(view_path),'sha256':digest(view_path.read_bytes())}

case_labels={'portrait':'Portrait desktop viewport','landscape':'Short landscape desktop viewport','large-text':'Enlarged text with emulated touch drag','round-ended':'Resolved public-proof scenario'}
state_labels={
 '01-concealed':'Initially concealed hand',
 '01a-emulated-touch-drag':'After emulated touch drag; no card selected',
 '02-revealed-selected':'Revealed hand; two cards selected',
 '02a-selection-limit':'Selection limit; three cards selected',
 '02b-deselected-last':'Last card deselected; two cards selected',
 '03-covered-again':'Hand covered again',
 '04-resumed-covered':'Covered after desktop foreground/resume commands',
}
expected_selected={'01-concealed':0,'01a-emulated-touch-drag':0,'02-revealed-selected':2,'02a-selection-limit':3,'02b-deselected-last':2,'03-covered-again':0,'04-resumed-covered':0}
comparison=json.loads((OWNER/'evidence/pixel-comparison.json').read_text())
records=[]; pairs=[]
for pair in comparison['comparisons']:
    case=pair['case']; filename=pair['capture']; state=Path(filename).stem
    left=OWNER/'evidence/baseline'/case/filename
    right=OWNER/'evidence/candidate'/case/filename
    assert left.read_bytes()==right.read_bytes(),(case,filename)
    pair_id=f'{case}/{state}'
    original_ids=[]
    for variant in ('baseline','candidate'):
        relative=f'{variant}/{case}/{filename}'
        original=OWNER/'evidence'/relative
        png=original.read_bytes()
        assert png[:8]==b'\x89PNG\r\n\x1a\n'
        dimensions=list(struct.unpack('>II',png[16:24]))
        assert dimensions==pair[variant+'_size']
        original_ref=reference(original,pair[variant+'_png_sha256'])
        report_path=original.parent/'report.json'; report=json.loads(report_path.read_text())
        run_path=original.parent/'receipt.json'; run=json.loads(run_path.read_text())
        diagnostics_path=original.with_suffix('.json'); diagnostics=json.loads(diagnostics_path.read_text())
        assert report['result']=='passed' and run['passed'] and run['exit_code']==0 and not run['engine_errors']
        assert any(observation.get('capture')==str(original) for observation in report['observations'])
        assert [report['width'],report['height']]==dimensions
        assert diagnostics['presentationMode']=='3d' and diagnostics['sceneStateApplied']
        assert int(diagnostics['selectedCount'])==expected_selected[state]
        assert '--path' in run['command'] and '--main-pack' not in run['command']
        assert run['command'][run['command'].index('--rendering-method')+1]=='gl_compatibility'
        fixture=Path(report['fixture']); fixture_data=json.loads(fixture.read_text())
        phase=fixture_data['payload']['game']['phase']
        label='Resolved round with public proof' if case=='round-ended' else state_labels[state]
        actual_view=relative in viewed
        if actual_view:
            assert original_ref['sha256']==viewed[relative]['sha256']
        equivalent_view=None
        if not actual_view:
            for seen_relative,seen in viewed.items():
                if seen['sha256']==original_ref['sha256']:
                    equivalent_view={'original_path':str(OWNER/'evidence'/seen_relative),'sha256':seen['sha256'],'viewer':'/root/assets','basis':'Exact byte identity permits reference to the recorded pixel observation; this original remains not directly viewed.','view_receipt':view_ref}
        record={
            'original_id':relative,'pair_id':pair_id,'variant':variant,
            'original_path':str(original),'original_filename':filename,
            'bytes':len(png),'sha256':original_ref['sha256'],'width':dimensions[0],'height':dimensions[1],
            'matches_original_owner_freeze':True,'gallery_relative_path':relative,
            'presentation_mode':'3d','scenario_id':case,'scenario_label':case_labels[case],
            'state_id':state,'state_label':label,'text_scale':report['textScale'],'fixture_phase':phase,
            'recorded_diagnostics':{k:diagnostics[k] for k in ('handConcealed','foreground','privateFaceCount','privateLabelCount','selectedCount','sceneStateApplied')},
            'original_capture_diagnostics':reference(diagnostics_path),
            'original_owner_result':reference(report_path),'original_owner_result_kind':report['kind'],'original_owner_result_scope':report['limitations'],
            'original_execution_receipt':reference(run_path),'execution_receipt_recorded_utc':run['captured_utc'],
            'per_image_capture_timestamp_utc':None,
            'execution_kind':'Desktop source project (--path), not a PCK execution.',
            'executed_pack_sha256':None,'actual_source_hashes':run['source_hashes'],
            'engine_binary_sha256':run['binary_sha256'],'fixture':reference(fixture),
            'actually_viewed':actual_view,'viewer':'/root/assets' if actual_view else None,
            'viewer_role':'source candidate owner' if actual_view else None,
            'direct_view_receipt':view_ref if actual_view else None,
            'direct_view_observation':viewed[relative]['observation'] if actual_view else None,
            'same_pixels_as_recorded_direct_view':equivalent_view,
            'view_status_label':'Direct owner view recorded' if actual_view else 'Unviewed original',
            'caption':f'3D · {case_labels[case]} · {report["textScale"]*100:g}% text · {label}. Local source capture; the paired baseline/candidate PNG is byte-identical.',
        }
        records.append(record); original_ids.append(relative)
    pairs.append({'pair_id':pair_id,'original_ids':original_ids,'byte_identical_png':True,'shared_sha256':digest(left.read_bytes())})

assert len(records)==40 and len({r['original_path'] for r in records})==40
assert len(pairs)==20 and sum(r['actually_viewed'] for r in records)==2
assert Counter(r['variant'] for r in records)=={'baseline':20,'candidate':20}
assert Counter(p['pair_id'].split('/')[0] for p in pairs)=={'portrait':6,'landscape':6,'large-text':7,'round-ended':1}
claims={
 'supported':[
    'All 20 recorded baseline/candidate PNG pairs are exact byte matches on the local Godot 4.7.2 OpenGL Compatibility/Xvfb/software-Mesa stack.',
    'The existing desktop scene check reports passed for portrait, landscape, enlarged-text/emulated-drag and public-proof scenarios for both source projects.',
    'The separate original owner validation reports 560 numbered checks passed: 306 redraw, 216 terminal-return and 38 sharing/lifetime assertions. Scene procedural assertions are separate.',
    'Only the two specified candidate originals have existing direct assets view attestations; per-original view flags preserve that distinction.'
 ],
 'limits':[
    'Images are source-project execution with no PCK input. Later integration/export identities must not be backfilled as the source of these captures.',
    'Exact image equality covers the recorded frames on this desktop stack; it does not prove every state, device driver or animation frame is identical.',
    'The hand uses a recipient-safe source fixture; no authority-accepted play, native accessibility or native gameplay qualification is claimed.',
    'Foreground/resume rows follow desktop renderer/controller commands and do not document native OS lifecycle gestures or snapshots.',
    'No native entry-latency improvement, native privacy-cover timing, shader compilation reduction or native qualification is established.',
    'run_check elapsed_seconds is test duration, not entry latency.',
    'Byte identity is distinct from actually viewing an original. Keep all 40 original capture identities even when hashes match.'
 ],
 'caption_exception':'The round-ended original filename 01-concealed.png is the generic first capture name. Its scenario label is Resolved round with public proof.'
}
map_data={
 'schema_version':1,'created_utc':NOW,'task_owner':'/root/assets','gallery_owner':'/root/review_design',
 'planned_gallery_root':GALLERY,'scope':'Publication metadata for existing originals only; no new capture, viewing, derivative, download or canonical edit.',
 'owner_original_root':str(OWNER),'counts':{'original_capture_identities':40,'baseline':20,'candidate':20,'byte_identical_pairs':20,'unique_image_sha256_values':len({r['sha256'] for r in records}),'directly_viewed_originals':2,'unviewed_originals':38},
 'execution_identity':{'kind':'desktop source execution','engine_version':'4.7.2.stable.official.ed1daf0bf','engine_binary_sha256':'8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e','rendering_method':'gl_compatibility','rendering_driver':'opengl3','display':'Xvfb','software_rendering':'Mesa llvmpipe; LIBGL_ALWAYS_SOFTWARE=1','msaa':'MSAA_2X; unchanged project/source setting','pack_input':None},
 'source_identity':{'baseline_snapshot':'source-c65e264/source-c65e264/godot/renderer','baseline_also_matches_diagnostic_renderer':'fa0fabb, as independently verified by review_game; no native capture claim','candidate_patch_sha256':source_refs['candidate_patch']['sha256'],'candidate_source_freeze_sha256':source_refs['candidate_source_freeze']['sha256'],'source_files_per_project':155,'changed_source_files':2,'related_retained_baseline_pack_sha256':'557b2297bed133a433acc25efa4837462465dd4e06da659ae5a4cbd792f77fe0','related_pack_scope':'Source-association context only. Neither baseline nor candidate screenshots were executed from this pack. No candidate PCK exists in these original source-run receipts.'},
 'source_and_validation_references':source_refs,'claims':claims,'originals':records,'pairs':pairs,
}
(HANDOFF/'source-map.json').write_text(json.dumps(map_data,indent=2)+'\n')
(HANDOFF/'receipts/referenced-originals.json').write_text(json.dumps({'created_utc':NOW,'scope':'Hash-bound original images and original metadata references. Files remain at their original paths.','files':list(references.values())},indent=2)+'\n')

md=['The handoff preserves all 40 original captures as 20 baseline/candidate pairs. Every pair is byte-identical on the recorded desktop stack. Two candidate originals have existing direct owner views; 38 originals remain unviewed. No image was captured, viewed, copied, decoded, transformed or downloaded for this handoff.','',f'Planned gallery root: `{GALLERY}`. review_design owns the gallery and mutable anchors. `source-map.json` contains complete per-original metadata and original receipt links; the table below keeps every original identity separate.','',
'All rows are the real 3D presentation executed from source with Godot 4.7.2 OpenGL Compatibility under Xvfb and software Mesa. Text scale and viewport dimensions come from the original reports. No PCK was an execution input. Foreground/resume names refer to the desktop checker’s renderer/controller commands. The round-ended first capture retains its original filename while using a public-proof scenario caption.','',
'| Gallery-relative original identity | Scenario / recorded state | Pixels / text | Original PNG | SHA-256 | Direct view |','| --- | --- | --- | --- | --- | --- |']
for r in records:
    md.append(f'| `{r["gallery_relative_path"]}` | {r["scenario_label"]} · {r["state_label"]} | {r["width"]} × {r["height"]} / {r["text_scale"]*100:g}% | [{r["original_filename"]}]({r["original_path"]}) | `{r["sha256"]}` | {"assets, prior direct view" if r["actually_viewed"] else "Unviewed"} |')
md+=['','Each record in [source-map.json](source-map.json) links the original capture diagnostics, case result, execution receipt, fixture and source hashes. The two viewed candidates also link [the existing-view attestation](receipts/owner-direct-views.json). A baseline counterpart may reference a matching pixel observation while retaining its own unviewed flag.','']
(HANDOFF/'MAPPING.md').write_text('\n'.join(md))

intro=[
'All 20 existing baseline/candidate Card3D PNG pairs match byte for byte. This handoff maps their 40 separate original capture identities for gallery publication; it creates no new images or canonical edits.','',
'Use [source-map.json](source-map.json) for original paths, filenames, byte counts, SHA-256 hashes, dimensions, 3D scenario/state labels, recorded text scale, diagnostics, execution/source references and per-original view status. [MAPPING.md](MAPPING.md) is the complete human-readable index. The planned gallery root is `docs/screenshots/godot-card3d-reuse-desktop-20260910`, with `baseline/` and `candidate/` children.','',
'Coverage is six portrait pairs, six short-landscape pairs, seven enlarged-text/emulated-touch pairs and one resolved public-proof pair. The two direct views are the selected-hand candidate images in portrait and enlarged text. They were viewed during the earlier validation pass by assets; the new attestation records that history and does not represent a new view. Other originals retain `actually_viewed=false`.','',
'These are source-project runs under Godot 4.7.2 OpenGL Compatibility, Xvfb and software Mesa, with unchanged MSAA_2X. Baseline source is frozen c65e264; the candidate is the two-file a904d39c resource-sharing patch. The original commands use `--path`; no PCK was the input. The associated retained baseline pack hash is contextual provenance only. Root’s later integration/export must remain a separate identity.','',
'Original desktop validation reports all four scene scenarios passed for both source projects, plus 560 numbered owner assertions across redraw, terminal-return and resource sharing/lifetime. Independent review_game verified the source delta, original receipts and exact image pairs, explicitly without viewing images. These checks and screenshots do not prove native entry latency, native cover timing, native accessibility or a shader-compilation reduction. The source checker uses a safe fixture and submits no authority-accepted gameplay.','',
'Original owner and independent evidence:','',
'| Evidence | Original file | SHA-256 |','| --- | --- | --- |']
for key in ('owner_freeze','candidate_patch','owner_result','owner_validation_summary','original_pixel_comparison','engine_version_receipt','rendering_review','rendering_review_freeze','security_source_review'):
    item=source_refs[key]
    intro.append(f'| {key.replace("_"," ")} | [{Path(item["original_path"]).name}]({item["original_path"]}) | `{item["sha256"]}` |')
intro+=['',
'Publication claims should stay with the recorded frames and source scope. Label the generic `round-ended/01-concealed.png` capture as the resolved public-proof scenario. Label foreground/resume states as desktop command checks and enlarged-text dragging as emulated touch. Keep all 40 paths even when hashes repeat, and retain explicit unviewed labels. The complete supported claims and limits are in `source-map.json`.','']
(HANDOFF/'HANDOFF.md').write_text('\n'.join(intro))

verification={'created_utc':NOW,'original_capture_paths_checked':40,'source_owner_hashes_checked':True,'all_images_match_owner_freeze':True,'all_capture_paths_found_in_original_case_reports':True,'all_case_results_and_exits_passed':True,'all_dimensions_and_text_scales_bound_to_reports':True,'all_modes_3d':True,'byte_pairs_checked':20,'byte_pairs_equal':20,'viewed_originals':2,'unviewed_originals':38,'new_captures':0,'new_direct_views':0,'image_files_written':0,'canonical_edits':0,'unique_image_sha256_values':len({r['sha256'] for r in records})}
(HANDOFF/'receipts/handoff-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
assert not list(HANDOFF.rglob('*.png'))
files=[]
for path in sorted(HANDOFF.rglob('*')):
    if path.is_file() and path.name!='freeze.json':
        files.append({'path':path.relative_to(HANDOFF).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes())})
(HANDOFF/'freeze.json').write_text(json.dumps({'created_utc':NOW,'status':'Bounded publication metadata complete; original images and receipts retained at referenced owner paths; review_design owns publication.','files':files},indent=2)+'\n')
print(json.dumps({'handoff_root':str(HANDOFF),'originals':40,'pairs':20,'direct_views':2,'new_image_work':0,'frozen_files':len(files),'bytes':sum(f['bytes'] for f in files),'hashes':{name:digest((HANDOFF/name).read_bytes()) for name in ('HANDOFF.md','MAPPING.md','source-map.json','receipts/owner-direct-views.json','receipts/handoff-verification.json','freeze.json')}},indent=2))
