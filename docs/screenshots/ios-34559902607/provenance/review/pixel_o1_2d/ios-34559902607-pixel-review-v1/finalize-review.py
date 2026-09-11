import json,hashlib,datetime,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
assert root.name=="ios-34559902607-pixel-review-v1"
reviewer="/root/pixel_o1_2d"
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(path):
    path=Path(path); data=path.read_bytes()
    return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
def write_new(name,doc):
    path=root/name; data=(json.dumps(doc,indent=2)+"\n").encode()
    with path.open("xb") as out:out.write(data)
    path.chmod(0o444)
    return identity(path)
plan_path=root/"integrity-review-plan.json"
plan_identity=identity(plan_path)
assert plan_identity["sha256"]=="f0a84deb3db4e6e33b4936d665d220942b63e3ad2dfa3abbaa3944c64d6461d3"
plan=json.loads(plan_path.read_text())
summary=json.loads((root/"summary.json").read_text())
captions=json.loads((root/"captions.json").read_text())["captions_by_review_position"]
assert summary["decision"]=="approved_with_scope_limits"
handoff_path=Path(plan["input_handoff"]["path"])
assert identity(handoff_path)==plan["input_handoff"]
handoff=json.loads(handoff_path.read_text())
assigned=sorted(handoff["priorityStills"]+handoff["companionStills"],key=lambda x:x["capture"]["exportMetadata"]["timestamp"])
assert len(assigned)==len(plan["source_records"])==9
logs={}; log_identities={}
for path in sorted(root.glob("direct-views-*.json")):
    doc=json.loads(path.read_text())
    assert doc["reviewer"]==reviewer and doc["run_id"]==34559902607
    for row in doc["direct_views"]:
        i=row["index"]
        assert i not in logs
        assert row["reviewer"]==reviewer and row["tool"]=="view_image" and row["detail"]=="original"
        assert row["batch"]==doc["batch"]
        logs[i]=row;log_identities[i]=identity(path)
assert sorted(logs)==list(range(8))
source_records=plan["source_records"]
observations=[x["original_sanitized_observation"] for x in source_records]
pre=plan["extra_observations"][0]["original_sanitized_observation"]
before=pre["controller"];after=observations[3]["controller"];receipt=after["lastViewerReceipt"]
assert receipt=={"accepted":True,"action":"PLAY_CARDS","error":None,"expectedRevision":"8","mode":"GODOT_2D","presentationOrdinal":"1","revision":"9","serial":"1","sessionGeneration":"1"}
assert before["lastViewerReceipt"] is None and before["sessionRevision"]==receipt["expectedRevision"]
assert before["sessionGeneration"]==after["sessionGeneration"]==receipt["sessionGeneration"]
assert before["presentationOrdinal"]==after["presentationOrdinal"]==receipt["presentationOrdinal"]
assert int(after["sessionRevision"])>=int(receipt["revision"])>int(receipt["expectedRevision"])
assert pre["port"]["native"]["intentEvents"]==0 and observations[3]["port"]["native"]["intentEvents"]==1
play=next(c for c in pre["port"]["renderer"]["controls"] if c["group"]=="partydeck_action_play")
assert play["visible"] is True and play["enabled"] is True and play["rect"]==[16,523,370,56]
assert play["clipRect"]==[0,0,402,657]
for i in [0,2,7,8]:
    renderer=observations[i]["port"]["renderer"]
    assert renderer["handConcealed"] is True
    assert (renderer["selectedCount"],renderer["privateFaceCount"],renderer["privateLabelCount"])==(0,0,0)
for i in [1,6]:
    renderer=observations[i]["port"]["renderer"]
    assert renderer["handConcealed"] is False and renderer["selectedCount"]==1
    assert renderer["privateFaceCount"]==renderer["privateLabelCount"]==5
    card=next(c for c in renderer["controls"] if c["group"]=="partydeck_hand_card" and c["cardIndex"]==0)
    assert card["selected"] is True
assert observations[1]["controller"]["lastViewerReceipt"]==observations[2]["controller"]["lastViewerReceipt"] is None
assert observations[6]["controller"]["lastViewerReceipt"]==observations[7]["controller"]["lastViewerReceipt"]
standard=observations[4];home=observations[5];later=observations[6]
assert standard["controller"]["mode"]=="COMPOSE" and standard["controller"]["sessionGeneration"]=="1"
assert standard["controller"]["phase"]=="ROUND_ENDED" and standard["port"]["renderer"] is None
assert standard["port"]["native"]["dormant"] and standard["port"]["native"]["emptyTree"]
assert home["controller"]["screen"]=="HOME" and home["controller"]["sessionPresent"] is False and home["controller"]["sessionGeneration"]=="2"
assert later["controller"]["sessionGeneration"]=="3" and later["controller"]["presentationOrdinal"]=="4"
assert later["port"]["native"]["presentationGeneration"]=="4"
assert later["port"]["native"]["processIdentifier"]==observations[0]["port"]["native"]["processIdentifier"]==98860
assert later["port"]["native"]["bootstrapCount"]==observations[0]["port"]["native"]["bootstrapCount"]==1
assert later["port"]["native"]["retainedIdentitiesMatchFirstEntry"]
assert observations[7]["observationSequence"]==observations[8]["observationSequence"]=="1299"
rows=[];gallery=[]
for i,(source,original) in enumerate(zip(source_records,assigned)):
    assert source["review_position_index_zero_based"]==i and source["original_handoff_row"]==original
    capture=original["capture"]; image_id=capture["original"]
    assert Path(image_id["path"]).stat().st_size==image_id["bytes"]
    assert source["independent_image_sha256"]==image_id["sha256"] and source["independent_image_bytes"]==image_id["bytes"]
    assert source["coverage_at_plan_creation"]=="unviewed"
    ri=source["byte_reference_review_position_index_zero_based"]
    assert ri in logs
    ref=source_records[ri]["original_handoff_row"]["capture"]
    assert ref["original"]["sha256"]==image_id["sha256"] and source["full_file_bytes_equal_to_reference"]
    direct=logs[ri]
    assert direct["path"]==ref["original"]["path"] and direct["sha256"]==ref["original"]["sha256"]
    assert direct["capture_label"]==ref["sourceAttachmentName"] and direct["capture_timestamp"]==ref["originalTimestampUtc"]
    reference={
      "reviewer":reviewer,"review_position_index_zero_based":ri,
      "original_capture_identity":ref,
      "direct_view_journal":log_identities[ri],
      "direct_view_batch":direct["batch"],
      "tool":"view_image","detail":"original",
      "tool_result_emitted_at_utc":direct["tool_result_emitted_at_utc"]
    }
    row={
      "review_position_index_zero_based":i,
      "reviewer":reviewer,
      "assigned_role":original["role"],
      "source_label_occurrence_by_original_timestamp":original["sourceLabelOccurrenceByOriginalTimestamp"],
      "original_capture_identity":capture,
      "dimensions":source["dimensions_from_png_ihdr"],
      "coverage":"direct" if i==ri else "reviewed_byte_match",
      "reviewed_reference":reference,
      "pixel_observation":direct["pixel_observation"],
      "caption":captions[str(i)],
      "paired_latest_sanitized_observation":original["pairedLatestSanitizedObservation"],
      "pairing_basis":original["pairingBasis"],
      "observation_attachment_minus_capture_timestamp_seconds":original["observationAttachmentMinusCaptureTimestampSeconds"],
      "full_observation_document_reference":{"receipt":plan_identity,"json_pointer":f"/source_records/{i}/original_sanitized_observation"},
      "identity_validation":{"png_bytes":source["independent_image_bytes"],"png_sha256":source["independent_image_sha256"],"full_file_bytes_equal_to_direct_reference":True,"paired_observation_identity_verified":True}
    }
    rows.append(row)
    gallery.append({
      "run_id":34559902607,"source_revision":plan["source_revision"],"reviewer":reviewer,
      "review_position_index_zero_based":i,"original_path":image_id["path"],"archive_member":image_id["archiveMember"],
      "bytes":image_id["bytes"],"sha256":image_id["sha256"],"dimensions":source["dimensions_from_png_ihdr"],
      "source_attachment_name":capture["sourceAttachmentName"],"original_timestamp_utc":capture["originalTimestampUtc"],
      "original_export_metadata":capture["exportMetadata"],"test_identifier":capture["testIdentifier"],
      "manifest_case_ordinal":capture["manifestCaseOrdinal"],"case_attachment_ordinal":capture["caseAttachmentOrdinal"],
      "occurrence_by_original_timestamp":original["sourceLabelOccurrenceByOriginalTimestamp"],
      "coverage":row["coverage"],"direct_reference_original_path":ref["original"]["path"],
      "direct_reference_sha256":ref["original"]["sha256"],"direct_reference_reviewer":reviewer,
      "direct_view_journal":log_identities[ri],"caption":row["caption"],
      "visibility_limits":direct["pixel_observation"]["limits"]
    })
assert sum(r["coverage"]=="direct" for r in rows)==8
assert sum(r["coverage"]=="reviewed_byte_match" for r in rows)==1
selected_paths={r["original_capture_identity"]["original"]["path"] for r in rows}
outside=[{"original_capture_identity":c,"coverage":"unviewed","reviewer":None,"reason":"Outside the nine assigned capture identities; no pixel observation claimed."} for c in handoff["allCaseCapturePointersInOriginalTimestampOrder"] if c["original"]["path"] not in selected_paths]
assert len(outside)==11
metadata_findings={
 "scope":"Interpretation of the paired original sanitized observations only; distinct from pixel conclusions.",
 "native_dimensions":{"png":{"width":1206,"height":2622},"renderer_viewport":pre["port"]["renderer"]["viewport"],"uikit_geometry":pre["port"]["geometry"]},
 "first_hide_sequence":{"selected_observation_sequence":"790","hidden_observation_sequence":"812","session_generation":"1","presentation_ordinal":"1","authority_receipt_unchanged":True},
 "play":{"pre_observation_identity":plan["extra_observations"][0]["original_handoff_pointer"],"pre_observation_sequence":"877","post_observation_sequence":"892","pre_play_control":play,"last_viewer_receipt":receipt,"post_controller_revision":"10","post_phase":"ROUND_ENDED","post_hand_count":4,"native_intent_events_before":0,"native_intent_events_after":1,"limitation":"No dedicated pre-Play PNG; rectangle/receipt evidence is not a screenshot of the tap instant."},
 "standard_return":{"observation_sequence":"911","session_generation":"1","phase":"ROUND_ENDED","renderer":None,"dormant":True,"empty_tree":True,"limitation":"No private-hand panel is visible in the Standard result PNG."},
 "fresh_practice":{"first_session_generation":"1","home_generation":"2","new_session_generation":"3","new_presentation_ordinal":"4","new_native_presentation_generation":"4","same_process_identifier":98860,"bootstrap_count":1,"retained_identities_match_first_entry":True,"selected_observation_sequence":"1264","hidden_observation_sequence":"1299","duplicate_milestone_observation_sequence":"1299"}
}
review={
 "schema_version":1,"reviewer":reviewer,"created_at_utc":now(),"run_id":34559902607,"attempt":1,"source_revision":plan["source_revision"],
 "case_identifier":plan["source_case_identifier"],"input_handoff":plan["input_handoff"],"integrity_plan":plan_identity,
 "summary_receipt":identity(root/"summary.json"),"captions_receipt":identity(root/"captions.json"),
 "decision":summary["decision"],"approved_scope":summary["approved_scope"],"coverage":summary["coverage"],
 "method":"Individually view eight distinct unchanged original PNG payloads at detail=original; retain the ninth source identity as a full-byte match to the actually viewed earlier second-Hide capture. Exact original case/name/ordinal/occurrence/export timestamp/path/bytes/SHA and paired observation metadata are preserved. Review activity is logged separately.",
 "blocking_pixel_defects":summary["blocking_pixel_defects"],"findings":summary["findings"],"limits":summary["limits"],
 "source_captures":rows,"outside_assignment_unviewed_captures":outside,"paired_observation_findings":metadata_findings,
 "prior_collector_and_package_receipts_not_reaudited":plan["prior_claims_not_reaudited"]
}
review_id=write_new("review.json",review)
gallery_id=write_new("gallery-caption-records.json",{"schema_version":1,"reviewer":reviewer,"run_id":34559902607,"review_receipt":review_id,"scope":"Nine assigned identities only; all other case captures remain outside this review.","records":gallery})
validation_id=write_new("validation.json",{
 "schema_version":1,"reviewer":reviewer,"validated_at_utc":now(),"status":"verified",
 "checks":{"exact_handoff_identity":True,"all_nine_source_rows_preserved":True,"unique_direct_journal_entries":8,"same_case_byte_match_references_actual_direct_view":True,"all_direct_views_original_detail":True,"all_captions_have_exact_image_identity":True,"coverage_counts":True,"outside_assignment_stays_unviewed":11,"paired_play_receipt_and_context_consistency":True,"fresh_practice_and_same_engine_context_consistency":True,"initial_integrity_plan_unchanged":True},
 "source_payload_hashes_repeated_during_finalization":False,
 "review_receipt":review_id,"gallery_caption_records":gallery_id,"coverage":summary["coverage"]
})
files=[]
for path in sorted(root.iterdir()):
    if path.is_file():
        assert path.name!="FROZEN.json"
        item=identity(path);item["relative_path"]=path.name;files.append(item)
frozen_id=write_new("FROZEN.json",{
 "schema_version":1,"status":"review-complete-frozen","reviewer":reviewer,"frozen_at_utc":now(),
 "run_id":34559902607,"source_revision":plan["source_revision"],"input_handoff":plan["input_handoff"],
 "decision":summary["decision"],"coverage":summary["coverage"],
 "review_receipt":review_id,"gallery_caption_records":gallery_id,"validation":validation_id,"files":files,
 "scope":"Bounded actual pixel review of nine current-run 2D original captures; no approval of outside-assignment images, offscreen content, continuous privacy, accessibility, physical devices or shipping."
})
for item in files:
    assert identity(item["path"])=={k:item[k] for k in ("path","bytes","sha256")}
assert len({r["original_capture_identity"]["original"]["path"] for r in rows})==9
assert root.stat().st_size>=0
for path in root.iterdir():
    if path.is_file():path.chmod(0o444)
root.chmod(0o555)
print(json.dumps({"frozen":frozen_id,"review":review_id,"gallery_captions":gallery_id,"validation":validation_id,"files_frozen":len(files),"coverage":summary["coverage"],"decision":summary["decision"]},indent=2))
