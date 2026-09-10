"""Record completed visual inspections; do not generate or publish derivatives."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

NOTES = json.loads("{\"baseline\":[\"Debug practice-after-play: round 1, Orbit catches Pip's three-Star bluff. Public Moon, Crown and Crown all mismatch. Pip uses light 1 and remains Still in. The named result and consequence are readable; Next round is partly clipped below the viewport.\",\"Optimized practice-after-play: round 1, Pip challenges Moxie's two-Crown claim. Public Crown and Wild both match; Pip loses the challenge and remains Still in after light 1. The named result and consequence are readable; only the top edge of the next-result action is visible.\",\"Both unchanged earlier smoke receipts record played_card as hand decreased by one. The later original PNGs show subsequent autonomous public results; these observations refer to different points in the flow.\",\"Both final Home diagnostics are captured at 200% text before environment restoration and show all Home actions. The separate preparation frame shows Launcher and is excluded.\"],\"api36\":[\"API36 debug normal Home shows full hero art and Host/Join/practice/How to play actions. Rules intro is readable; the intermediate rules-last-step capture clips earlier text at the top and shows only the upper edge of the practice action.\",\"The dedicated normal rules-practice-action capture shows the complete rounded Practice button and label. The subsequent rules-practice-entered capture already shows an autonomous truthful-Star result: Pip challenged Moxie, Pip burned out on light 1; the next-result action clips at the bottom. It is not a concealed entry frame.\",\"Normal settings show sound off, haptics off and reduced motion on; the saved-settings capture agrees after relaunch. Return Home has complete visible actions.\",\"API36 debug practice-concealed and resumed frames hide private faces/rank labels and selection; normal Show hand, select/challenge controls and Moon/turn context fit.\",\"The selected normal hand shows five cards, a selected Star check, 1 of 3 selected, claim 1 Moon and complete Play 1 card / Challenge Orbit controls.\",\"Debug practice-after-play shows Guest's one-Moon bluff caught by Moxie with public Star and light-1 Still in explanation. Next round is partly clipped at the bottom; the smoke run does not submit this result action.\",\"Host lobby and after-share show one ready local host, five empty seats, invitation entry and disabled Deal; no live invitation or QR is exposed. Normal Join name field and actual keyboard are visible together.\",\"API36 debug invalid Join shows named field, deliberately invalid invitation, readable recovery error and complete Join action. The 200% invalid form is scrolled, with title and part of the name-field label above the viewport; error and Join action fit.\",\"Enlarged Home retains Host, Join, practice, How to play and settings actions. Enlarged Rules text reflows; intermediate pages clip at viewport edges. The dedicated 200% Practice button has its full label and borders visible.\",\"The enlarged Rules entry is a concealed round-1 Moon table with complete Show hand. All three enlarged settings switches remain readable; lower credits/details scroll beyond the viewport.\",\"At 200%, focused Join name and its complete input border remain above the real keyboard. The enlarged hand is a vertical list; the first capture clips the lower Crown card, while the later action capture shows all five cards and full Play 1 card / Challenge Orbit actions. Earlier round/turn context has scrolled above. No 200% play submission is recorded.\",\"API36 optimized normal Home and Settings match the expected complete layouts; sound/haptics remain off and reduced motion on after relaunch.\",\"Normal Rules pages scroll; the intermediate last-step frame does not show the complete final practice action. Its dedicated practice-action capture shows the full rounded button and label.\",\"The optimized normal Rules entry already shows an autonomous truthful-Moon result: Orbit challenged Pip and stays in after light 1. The Next round label is visible but the action's lower boundary reaches beyond the viewport; this result action is not exercised.\",\"API36 optimized normal concealed/resumed Star-table frames hide all private faces and ranks. Selected normal hand shows five cards, one Star selection and complete Play/Challenge controls; current turn/table/claim remains readable.\",\"Optimized practice-after-play is a later public truthful result: Pip challenged Moxie's two-Star claim; public Star and Wild both match, and Pip burns out at light 1. Named result and consequence are readable; the Next action is entirely below the captured viewport. The original earlier observation still records hand decreased by one.\",\"Optimized host lobby/after-share contain no live QR or invitation. The normal Join name field and actual keyboard fit together.\",\"API36 optimized enlarged Home retains all launch/help/settings actions. Rules text reflows and scrolls; the intermediate last-step frame clips at both viewport edges, while the dedicated Practice action shows its full label and rounded border.\",\"The enlarged Rules entry is a concealed round-1 Star table with complete Show hand. Enlarged settings expose all three switches; lower explanatory text continues below.\",\"The enlarged focused name field and real keyboard fit together. At the enlarged invalid-Join capture, the recovery error is readable but the Join button's bottom clips; recorded input geometry establishes reachability at the tapped position.\",\"The enlarged hand uses a vertical list and its first capture clips the fifth Star card. The later action capture shows all five cards, claim text and complete Play / Challenge actions. Earlier table/turn context has scrolled above. The 200% phase does not submit a play.\"],\"api36_sheets_seen\":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19],\"baseline_direct\":[\"/tmp/partydeck-android-production-native-34456441354/extracted/10144559609-android-jvm-reports/build/ci/android/debug/practice-after-play.png\",\"/tmp/partydeck-android-production-native-34456441354/extracted/10144559609-android-jvm-reports/build/ci/android/optimized-test-signed/practice-after-play.png\"],\"final_classification\":{\"inspected_sheets\":[\"/tmp/partydeck-gallery-visual-review/queued-android/34456441354-final-and-preparation.png\",\"/tmp/partydeck-gallery-visual-review/queued-android/34457458638-final-and-preparation.png\"],\"findings\":[\"Both final-screen.png originals in each run show the ordinary PartyDeck Home screen with Host, Join, practice, How to play and settings actions visible. All four are eligible app diagnostics.\",\"Each preparation/attempt-1/final-screen.png shows the pre-install Android Launcher. Both remain excluded preparation images.\",\"The final diagnostics follow the 200% flow and precede restore_environment in the exact harness. Their font scale is 2.0; they are app Home diagnostics after leaving practice.\",\"No live invitation, QR or Sharesheet is visible in these six originals.\"],\"eligible_originals_per_run\":62,\"preparation_exclusions_per_run\":1,\"harness_sha256\":\"7d6cef007b3d4fb64c6aaaf2e55c3039dc02853332607ccba4a239bc8cd1e5f3\"}}")
AUDIT_PATH = Path('/tmp/partydeck-gallery-1584-source-audit.json')
AUDIT = json.loads(AUDIT_PATH.read_text())

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

assert sha(AUDIT_PATH) == 'd586ac480bf729c7e3e3d8e30822e663c088ab027778150a97abc347caaf176e'
assert NOTES['api36_sheets_seen'] == list(range(20))
for batch in AUDIT['batches']:
    run = batch['run']
    api36 = batch['api'] == 36
    captures = batch['captures']
    finals = [c for c in captures if c['stage'] == 'final-screen']
    routes = [c for c in captures if c['stage'] != 'final-screen']
    assert len(finals) == 2 and len(routes) == 60
    final_sheet = Path('/tmp/partydeck-gallery-visual-review/queued-android') / (run + '-final-and-preparation.png')
    sheets = []
    if api36:
        for sheet in AUDIT['review_sheets']:
            sheets.append({**sheet, 'sha256': sha(sheet['path']), 'bytes': Path(sheet['path']).stat().st_size,
                'visually_inspected': True, 'published_in_gallery': False,
                'eligible_originals': sheet['originals'], 'excluded_preparation_originals': []})
    sheets.append({'path': str(final_sheet), 'sha256': sha(final_sheet), 'bytes': final_sheet.stat().st_size,
        'derived_review_sheet_only': True, 'visually_inspected': True, 'published_in_gallery': False,
        'eligible_originals': [c['source_original'] for c in finals],
        'excluded_preparation_originals': [c['source_original'] for c in batch['excluded']]})
    review = {
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'reviewer': 'review_design',
        'ci_run': run,
        'source_revision': batch['source_revision'],
        'source_revision_exact': True,
        'source_audit': {'source_original': str(AUDIT_PATH), 'sha256': sha(AUDIT_PATH)},
        'earlier_owner_receipt': batch['owner_frozen_receipt'],
        'earlier_owner_review_attribution': 'review_game' if not api36 else 'API 36 independent audit owner; see original final-receipt.json',
        'earlier_owner_visual_review_unchanged': batch['earlier_owner_visual_review'],
        'originals': captures,
        'review_sheets': sheets,
        'excluded_preparation_originals': batch['excluded'],
        'gallery_reviewer_originals_inspected': 62 if api36 else 4,
        'gallery_reviewer_route_originals_inspected': 60 if api36 else 2,
        'gallery_reviewer_final_originals_inspected': 2,
        'originals_covered_by_owner_and_gallery_visual_reviews': 62,
        'owner_route_originals_reviewed': [] if api36 else [c['source_original'] for c in routes],
        'originals_directly_viewed_by_gallery_reviewer': [] if api36 else NOTES['baseline_direct'],
        'visual_findings': NOTES['api36'] if api36 else NOTES['baseline'],
        'final_diagnostic_classification': NOTES['final_classification']['findings'],
        'exact_harness_sha256': NOTES['final_classification']['harness_sha256'],
        'font_scales': [1.0, 2.0],
        'final_diagnostics_font_scale': 2.0,
        'final_diagnostics_precede_environment_restore': True,
        'large_text_play_submitted': False,
        'native_next_round_exercised': False,
        'live_invitation_qr_sharesheet_captures_present': False,
        'numeric_margins_transferred_from_older_collections': False,
        'all_content_simultaneously_fits_claimed': False,
        'new_application_executions': 0,
        'new_builds_or_runtime_tests': 0,
        'git_commands_run': 0,
        'limits': [
            'Static image review and original input receipts do not qualify screen-reader behavior, physical devices, mixed-device LAN, camera frames or store distribution.',
            'Godot session smoke was explicitly disabled in these ordinary app runs.',
            'Public result images may follow an earlier played_card observation; original receipts remain unchanged.',
            'Contact sheets are review derivatives retained outside the gallery. Published thumbnails use the unchanged original PNGs.',
            'API 36 package identity is receipt-based; the full APK artifact was not downloaded for this review.' if api36
            else 'The owner reviewed 60 named route originals in ten paired sheets. This later gallery review inspected two final originals plus two overlapping after-play originals.'
        ]
    }
    seen = {p for s in sheets for p in s['eligible_originals']}
    seen.update(review['originals_directly_viewed_by_gallery_reviewer'])
    assert len(seen) == review['gallery_reviewer_originals_inspected']
    assert seen | set(review['owner_route_originals_reviewed']) == {c['source_original'] for c in captures}
    path = Path('/tmp/partydeck-gallery-1584-visual-review-' + run + '.json')
    assert not path.exists()
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'path': str(path), 'sha256': sha(path), 'reviewer_originals': len(seen), 'eligible_originals_covered': 62}))
