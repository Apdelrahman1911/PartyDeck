#!/usr/bin/env python3
"""Seal manual visual findings; this script does not perform image review."""

import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


BASE = Path('/root/projects/PartyDeck/artifacts/evidence-storage')
ROLE = BASE / 'restart-20260911T0457/ios_review'
RUN = BASE / '34559902607'
REVIEWER = '/root/ios_review'
PIXEL_PATH = ROLE / 'original-screenshot-independent-review-v1.json'
ROLLUP_PATH = ROLE / 'ios-independent-review-rollup-v1.json'


def record(path, data=None):
    path = Path(path)
    if data is None:
        data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def pinned_json(path, expected_sha, expected_bytes=None):
    data = Path(path).read_bytes()
    ref = record(path, data)
    assert ref['sha256'] == expected_sha, (str(path), ref)
    if expected_bytes is not None:
        assert ref['bytes'] == expected_bytes, (str(path), ref)
    return json.loads(data), ref


assert not PIXEL_PATH.exists(), 'Immutable pixel receipt already exists'
assert not ROLLUP_PATH.exists(), 'Immutable role rollup already exists'

results, results_ref = pinned_json(
    ROLE / 'dedicated-native-results-independent-review-v1.json',
    '5a79f8b0450a6a0527b7ddf3438f501c23d0fc66ab773f2852ec9e575e2fdc53', 204620)
ordinary, ordinary_ref = pinned_json(
    RUN / 'ordinary-and-uikit-outcomes-v1.json',
    '9409c5f218a7b2570693e38839d6f2d1bcb550585815514be48df68448084bb5', 33085)
production, production_ref = pinned_json(
    RUN / 'production-session-outcome-v1.json',
    '03a2bf55ea8f9351b7eab0ce3ad2035c4656d78ffe01b3e538d19ff9f6aab956', 365810)
_, collection_ref = pinned_json(
    RUN / 'collection-complete.json',
    '2b67bf344eaf96a341dc86d700ef0db01442d31969c8e2c414583a85bc80571e')

prior_records = {}
for name, sha, size in [
    ('native-review-readiness-v1.json', '81ac74dbbf593c95b13b20c33a4c27a35a64cf58ebc61445ce56c1bd91e2d62c', 14209),
    ('native-log-independent-review-v1.json', '9ef77741a7f7cb60361a8885fdcb9e2b655ae7c752bb81751f06665774dcd94f', 15684),
    ('dedicated-auditor-source-independent-review-v1.json', 'a6b5061d5b22185df41b8699bf247ff145d99ded926bb53e07ab4ce8330d23c8', 19116),
    ('shared-native-junit-independent-review-v1.json', '7d4aea7decacf4d22c8964c1b529a4b005b4258a7f26f94b550b046348fc42fb', 21124),
    ('prior-source-binding-check-reconstructed-v1.json', '0a865734f5b8d30580f94b94f63eeed28ecc8f02e5ed8fab9149df2d5b33853a', None),
    ('prior-source-binding-reconstruction-provenance-v1.json', '973e31338627a60c4599f1fd9c2203c73330a78feb10529eb2c94f0c8a06bc24', None),
]:
    _, prior_records[name] = pinned_json(ROLE / name, sha, size)

timing_path = BASE / 'restart-20260911T0457/ios_fix/ACTUAL-TIMING-INTERPRETATION-34559902607-v2.json'
timing_ref = record(timing_path)
assert timing_ref['bytes'] == 42737
assert timing_ref['sha256'] == '18d8a370f2f21e7787034c6087824c3449c2770ec435c9750adebfa1c474e29e'

FINDINGS = {}
MANUAL = {}


def finding(key, statement, names):
    assert key not in FINDINGS
    FINDINGS[key] = {'visibleFinding': statement, 'basis': 'Direct view of each named original PNG by the independent reviewer'}
    for name in names.split():
        assert name.endswith('.png')
        MANUAL.setdefault(name, []).append(key)


# These file assignments record the actual manual views across the review
# continuation. They are not inferred from filenames, success gates or JSON.
finding('standard_concealed',
    'The captured Standard hand area shows the concealed hand panel and Show hand control; no private hand faces, rank labels or selected-card markers are visible.',
    '''30F6BE67-8F7C-4579-82C5-D8354FBB1DC1.png
       BA0FFB78-590E-44AC-BEF4-430B1604479F.png
       20C41AFB-81AD-4F3B-A568-233DBF5C4330.png
       6902B013-E409-49DE-8B2A-A1E177999B50.png
       37645B95-59ED-4575-8FBE-5A57A43799AB.png
       2C4189F4-8E3A-4AEC-836F-E2D62A782A33.png''')
finding('standard_five_visible_unselected',
    'Five card faces and readable labels are simultaneously visible in the Standard hand. The selection text is 0 of 3 selected, with no selected-card checks visible.',
    '''4F3265E9-3332-476A-94A5-52D730FE2CB4.png
       BF6A4215-6134-4742-AD8E-7CDF2EA041AA.png
       B9F21E9C-8967-422A-87A8-B65F2644A63B.png
       609DDEB3-25F9-4AD4-8985-E127453A1F94.png
       B74A1E74-163C-45EF-ACE0-3FCFC663B537.png
       59050287-1F7F-490B-AC7A-51E6024FF430.png''')
finding('standard_three_selected_and_limit_feedback',
    'Exactly the first three of five visible Standard cards have selected markers. The screen reads 3 of 3 selected and Choose up to 3 cards.; the Play 3 cards control is visible.',
    '''0FF55D21-15F2-48CE-BA7F-92A4D7443CFD.png
       9C8D8812-4C4A-40C9-9EA6-99351E77F7CF.png
       3CF5875D-126E-4082-9C7E-06B6909A55A2.png''')
finding('native_2d_concealed',
    'The 2D native hand is covered, with 5 cards, covered and Reveal visible. No private hand faces, rank labels or selected-card markers are visible.',
    '''B34C60A8-EA61-4820-B60D-BDE87C8323FE.png
       85E50C54-A954-4B72-87BD-3A82DD53CBDD.png
       BCA52D0A-4F90-4349-BAD9-B77B60D738AE.png
       DF6233B3-E4AE-462A-9979-F604368BA980.png''')
finding('native_2d_first_card_selected',
    'The 2D native hand strip shows a selected first card with check and border and readable visible card labels. Only part of the horizontal hand strip is simultaneously onscreen; this is not visual evidence that all five 2D native cards fit at once.',
    '''872023E0-6770-4413-8B0B-7024E4075737.png
       D4FBA53E-D71B-4806-85D2-E23139858D15.png''')
finding('native_3d_concealed',
    'The 3D native hand shows five covered card backs, with no private hand face labels or selected-card marker visible.',
    '''2BCEDF04-EE2E-42EE-B765-AC5DB90D88EA.png
       910A258C-3158-4B80-B83A-7C0C0EFB02C9.png
       0C7AC701-1E72-42CC-A68A-6D1AC1EFB6B3.png
       D2EA5FDE-7418-4EB5-B70A-52C5C484D447.png''')
finding('native_3d_first_card_selected',
    'All five 3D native card faces and labels are visible, with the first-card selected marker present.',
    '''BEFA0FD5-DCE1-4749-84EE-96E7B6EDD1AD.png
       96BF308F-29B0-4BF5-B689-8B874FF80130.png''')
finding('native_public_round_result',
    'The native capture shows public round-result content after Play. Public result-card disclosure is visible; it is distinct from private concealed-hand content. Action acceptance comes from the separately reviewed receipt, not these pixels.',
    '''545A5EEB-3CA6-445A-8409-574FA9EFEF48.png
       8741B976-69BE-4AF4-8751-1D668B1DCAD5.png''')
finding('standard_public_round_result',
    'The Standard return shows the public round-result screen. No native stage or private hand disclosure is visible in this capture.',
    '''FDDF061A-3803-44AB-AB9D-968D76BBF1FB.png
       3B2EF600-E81D-4789-AC94-8149D93DAC6D.png''')
finding('next_round_2d_immediate_visual_limitation',
    'Despite its accepted NEXT_ROUND source label, this immediate 2D Standard capture still shows the preceding result panel and Next round control. Round 2 is not visually established by this image.',
    'F9BC2B55-1C77-4851-AD6B-E4DA3A07601D.png')
finding('standard_round_two_concealed',
    'The Standard table visibly shows ROUND 2 and a concealed hand, with no Leave dialog or native stage visible.',
    '''08D65E9E-794B-4E0B-8EFE-22DA74BB22EB.png
       6221652C-F7DD-45DD-A284-0FC83E6C1414.png
       A6E03DED-D494-4139-81C3-49FD68CB8FEC.png''')
finding('leave_dialog',
    'The Leave the table? modal and Leave and Stay controls are visible above the Standard underlay. No private hand disclosure or native stage is visible.',
    '''8A23C534-7D00-41C2-93E2-9526DAE8B23A.png
       E1F8D7E2-5FBA-47BE-A7B3-C1B537580881.png
       9960E985-75EF-41BF-ACBD-8A1E69A92332.png
       A1AE82BE-A106-4089-8ED9-3DC03C029FE3.png
       62D9A565-0EEF-4B9E-908B-DA8E8FEDBB11.png
       7F81DB0A-2BE1-446E-A003-8D183360D5D1.png''')
finding('home',
    'Home is visible with Host, Join and Practice choices. No native stage or private hand content is visible.',
    '''2593E026-0033-4E04-8C79-6CA11D2FF597.png
       42615FED-42C2-4100-ACF7-A5D4B20752C8.png
       D52FC7CE-FE18-49B6-A5BA-BD01FA7D3831.png
       6E61EF7D-0A35-4A58-BB49-3B72B69AA90C.png
       BA4FE395-6EF1-4FCE-A00F-65AC98BB248A.png''')
finding('native_3d_whole_controls_after_scroll',
    'The actual post-scroll 3D image visibly includes the complete Play 1, Challenge Orbit and Return to lobby buttons, with the first-card selected marker retained. This image supports whole-button visibility after scrolling; it does not demonstrate Challenge execution.',
    '0896A2DA-8FFA-4722-8D67-4BA569111EC9.png')
finding('settings',
    'Settings shows Sound, Haptics and Reduce motion toggles with explanatory text. The lower credits link is clipped by the scrolling viewport, so this capture does not establish complete initial visibility of that link.',
    '3D66B340-AADF-445F-A14E-49C9D080D6DC.png')
finding('host_lobby',
    'The host lobby shows Native Host ready, one of six seats filled and five open seats. Invite is visible and Deal appears disabled. No invitation payload or admission secret is visible in these lobby captures.',
    '''27A99B04-983E-4093-BBD5-856857AAAAB0.png
       AABDA185-1C33-418B-84CB-0BD1E6E78E5A.png''')
finding('ordinary_public_round_result',
    'The ordinary practice capture shows a public round result with the revealed public card and opponent result/fuse information. The lower next action is partly clipped by the scrolling viewport.',
    'F28F669C-C729-4085-8599-E1336112B96C.png')
assert len(MANUAL) == 51

finding('native_3d_initial_bottom_clipping',
    'The initial unscrolled 3D viewport visibly clips the bottom Return to lobby action. These initial images do not establish full action-button bounds; the separate actual post-scroll image does.',
    '''2BCEDF04-EE2E-42EE-B765-AC5DB90D88EA.png
       BEFA0FD5-DCE1-4749-84EE-96E7B6EDD1AD.png''')
finding('ordinary_home_no_qualification_marker',
    'The ordinary Home capture has no visible Q qualification marker.',
    'BA4FE395-6EF1-4FCE-A00F-65AC98BB248A.png')

ordinary_labels = {
    'BA4FE395-6EF1-4FCE-A00F-65AC98BB248A.png': 'Home',
    '3D66B340-AADF-445F-A14E-49C9D080D6DC.png': 'Settings',
    '27A99B04-983E-4093-BBD5-856857AAAAB0.png': 'Native host lobby',
    'AABDA185-1C33-418B-84CB-0BD1E6E78E5A.png': 'Native host invitation closed',
    'F28F669C-C729-4085-8599-E1336112B96C.png': 'Practice after accepted play',
    '37645B95-59ED-4575-8FBE-5A57A43799AB.png': 'Practice Standard concealed',
    'B74A1E74-163C-45EF-ACE0-3FCFC663B537.png': 'Practice Standard all five native card descriptions',
    '3CF5875D-126E-4082-9C7E-06B6909A55A2.png': 'Practice Standard maximum selection and count-only feedback',
    '2C4189F4-8E3A-4AEC-836F-E2D62A782A33.png': 'Practice Standard Hide removes private nodes and selection',
    '59050287-1F7F-490B-AC7A-51E6024FF430.png': 'Practice Standard fresh Reveal is unselected',
}

records_by_path = {r['path']: r for r in results['originalRecords']}
owner_captures = {p['original']['path']: p for p in production['capturePointers']}
owner_observations = {p['original']['path']: p for p in production['observationPointers']}
manifest_refs = {m['scope']: m['original'] for m in results['originalManifests']}
production_entries = []
chronological_occurrences = Counter()

for index, pair in enumerate(results['sourceNamedCaptureObservationPairs']):
    capture = copy.deepcopy(pair['capture'])
    observation = copy.deepcopy(pair['observation'])
    owner = owner_captures[capture['original']['path']]
    owner_observation = owner_observations[observation['original']['path']]
    name = Path(capture['original']['path']).name
    assert name in MANUAL
    assert capture['original'] == records_by_path[capture['original']['path']]
    assert observation['original'] == records_by_path[observation['original']['path']]
    assert all(capture['original'][k] == owner['original'][k] for k in ('path', 'bytes', 'sha256'))
    assert capture['sourceAttachmentName'] == owner['sourceAttachmentName']
    assert capture['testIdentifier'] == owner['testIdentifier']
    assert capture['caseAttachmentOrdinal'] == owner['caseAttachmentOrdinal']
    assert capture['exportMetadata'] == owner['exportMetadata']
    for member, owner_member in ((capture, owner), (observation, owner_observation)):
        member['manifestCaseOrdinal'] = owner_member['manifestCaseOrdinal']
        member['sameSourceLabelOccurrenceInManifest'] = owner_member['sameSourceLabelOccurrenceInManifest']
    key = (capture['testIdentifier'], capture['sourceAttachmentName'])
    chronological_occurrences[key] += 1
    production_entries.append({
        'capture': capture,
        'manifestScope': 'production-sessions',
        'sameCaptureLabelOccurrenceChronologically': chronological_occurrences[key],
        'pairedSanitizedObservation': observation,
        'observationMinusCaptureSeconds': pair['deltaSeconds'],
        'independentResultPairJsonPointer': f'/sourceNamedCaptureObservationPairs/{index}',
        'directlyViewedByIndependentReviewer': True,
        'visualFindingIds': MANUAL[name],
    })

ordinary_entries = []
for owner_index, pointer in enumerate(ordinary['exportedAttachmentPointers']):
    name = Path(pointer['original']['path']).name
    label = ordinary_labels[name]
    original = {k: pointer['original'][k] for k in ('path', 'bytes', 'sha256')}
    assert original == records_by_path[original['path']]
    assert pointer['exportMetadata']['suggestedHumanReadableName'].startswith(label + '_0_')
    ordinary_entries.append({
        'capture': {
            'testIdentifier': pointer['testIdentifier'],
            'manifestCaseOrdinal': pointer['manifestCaseOrdinal'],
            'caseAttachmentOrdinal': pointer['caseAttachmentOrdinal'],
            'sameRawLabelOccurrenceInManifest': pointer['sameRawLabelOccurrence'],
            'sourceAttachmentName': label,
            'original': original,
            'exportMetadata': copy.deepcopy(pointer['exportMetadata']),
        },
        'manifestScope': 'ordinary',
        'ownerOutcomePointer': f'/exportedAttachmentPointers/{owner_index}',
        'pairedSanitizedObservation': None,
        'observationPairingNote': 'No source-named sanitized observation is paired with this ordinary screenshot.',
        'directlyViewedByIndependentReviewer': True,
        'visualFindingIds': MANUAL[name],
    })

assert len(production_entries) == 41
assert len(ordinary_entries) == 10
all_entries = production_entries + ordinary_entries
assert {Path(e['capture']['original']['path']).name for e in all_entries} == set(MANUAL)
assert all(e['directlyViewedByIndependentReviewer'] for e in all_entries)
assert results['observedAttachments']['uikitCaptures'] == 0


def image_pointer(name):
    matches = [f'/{group}/{i}'
               for group, entries in [('productionCaptures', production_entries), ('ordinaryCaptures', ordinary_entries)]
               for i, entry in enumerate(entries)
               if Path(entry['capture']['original']['path']).name == name]
    assert len(matches) == 1
    return matches[0]


limitations = [
    {
        'id': 'immediate_2d_next_round_pixels',
        'captureJsonPointer': image_pointer('F9BC2B55-1C77-4851-AD6B-E4DA3A07601D.png'),
        'finding': 'The immediate accepted NEXT_ROUND capture still displays the preceding result panel, not round 2.',
        'acceptedStateEvidence': 'Its paired sanitized accepted COMPOSE NEXT_ROUND receipt independently records round 2; dedicated-native-results-independent-review-v1.json establishes acceptance.',
        'laterVisualEvidenceJsonPointer': image_pointer('08D65E9E-794B-4E0B-8EFE-22DA74BB22EB.png'),
        'laterVisualFinding': 'The later 2D Leave-cancel capture visibly shows ROUND 2 with a concealed hand and no dialog.',
        'scope': 'A limitation of the immediate visual evidence. It does not negate the accepted authority action and does not establish a persistent rendering defect.',
    },
    {
        'id': 'capture_and_observation_are_not_atomic',
        'finding': 'The source takes a screenshot and then attaches the latest sanitized lastDocument. Exact case, source label and close timestamps bind the exported evidence sequence, not an atomic rendered frame and authority state.',
        'sourceReviewReceipt': prior_records['dedicated-auditor-source-independent-review-v1.json'],
        'scope': 'Do not claim that every capture is a pixel-exact realization of its paired observation.',
    },
    {
        'id': '3d_initial_viewport_and_scrolled_bounds',
        'initialExamples': [image_pointer('2BCEDF04-EE2E-42EE-B765-AC5DB90D88EA.png'), image_pointer('BEFA0FD5-DCE1-4749-84EE-96E7B6EDD1AD.png')],
        'postScrollCaptureJsonPointer': image_pointer('0896A2DA-8FFA-4722-8D67-4BA569111EC9.png'),
        'finding': 'Initial unscrolled 3D frames clip the bottom Return to lobby action. The actual post-scroll image shows all three full action buttons and retained selection.',
        'scope': 'Whole-button coverage is accepted for the actual post-scroll checkpoint. Challenge action execution is not claimed.',
    },
    {
        'id': '2d_horizontal_hand_viewport',
        'captures': [image_pointer('872023E0-6770-4413-8B0B-7024E4075737.png'), image_pointer('D4FBA53E-D71B-4806-85D2-E23139858D15.png')],
        'finding': 'Native 2D selections show part of a horizontal hand strip. All five 2D native cards are not simultaneously visible in these captures.',
    },
    {
        'id': 'ordinary_lower_scroll_content',
        'captures': [image_pointer('3D66B340-AADF-445F-A14E-49C9D080D6DC.png'), image_pointer('F28F669C-C729-4085-8599-E1336112B96C.png')],
        'finding': 'The ordinary Settings credits link and practice result next action are partly clipped in their captured scrolling viewports.',
    },
    {
        'id': 'qualification_images',
        'finding': 'Small Q qualification markers are visible in production Standard/Home captures. These are Debug Simulator qualification images; the shipping-picker steps were skipped.',
        'scope': 'No shipping screenshot or shipping-picker execution approval.',
    },
]

now = datetime.now(timezone.utc).isoformat()
pixel = {
    'schemaVersion': 1,
    'reviewedAtUtc': now,
    'reviewer': REVIEWER,
    'runId': 34559902607,
    'attempt': 1,
    'headSha': '39405bb0fd6ba0214e70ed251aab1f9f571dc9aa',
    'nativeJobId': 103140623784,
    'disposition': 'Direct visual review complete with explicit capture limitations',
    'reviewMethod': {
        'imageTool': 'tools.view_image',
        'originalPngsDirectlyViewed': 51,
        'production': 41,
        'ordinary': 10,
        'uikit': 0,
        'attribution': 'The independent reviewer directly viewed all 51 original paths across this review continuation, including both same-byte host lobby images. Counts do not substitute collector statements or byte matches for a direct view.',
        'display': 'The image tool displayed the original files using its default view rendering. This is substantive visible-content review, not an automated image comparison or exhaustive accessibility audit.',
        'integrity': 'Original manifest/member hashes were independently checked in the pinned dedicated result receipt. This sealing script copies those verified references and checks receipt consistency; it does not rehash the PNGs, ZIP, job log or source tree.',
        'sealingScript': record(Path(__file__)),
        'scriptRole': 'Serializes manually supplied visual findings and verifies their exact membership/pointers. Rerunning this script does not repeat the visual inspection.',
    },
    'originalCollectionReceipt': collection_ref,
    'originalIntegrity': results['originalIntegrity'],
    'originalInventory': results['originalInventory'],
    'originalRetention': 'Canonical paths refer to the newly collected originals. Earlier temporary originals were deleted during the restart; this review does not attribute them as surviving.',
    'priorIndependentResultReceipt': results_ref,
    'ownerOutcomeReceipts': {'ordinaryAndUIKit': ordinary_ref, 'production': production_ref},
    'originalManifests': manifest_refs,
    'ordering': 'Production entries follow the independent result receipt chronology; manifest case/attachment/label-occurrence ordinals remain original manifest order, which is reverse chronological. Ordinary entries retain owner manifest order.',
    'findingCatalog': FINDINGS,
    'productionCaptures': production_entries,
    'ordinaryCaptures': ordinary_entries,
    'actual3DBodyScrollNonPixelEvidence': {
        'source': results_ref,
        'jsonPointer': '/bodyScrollReview',
        'original': results['bodyScrollReview']['original'],
        'coverage': results['bodyScrollReview']['coverage'],
        'before': results['bodyScrollReview']['before'],
        'after': results['bodyScrollReview']['after'],
        'fullBoundsAndAllSourceInputPrivacyInvariantsIndependentlyChecked': True,
        'nativeChallengeExecuted': False,
        'pixelEvidenceJsonPointer': image_pointer('0896A2DA-8FFA-4722-8D67-4BA569111EC9.png'),
        'distinction': 'The prior observation review establishes exact input/privacy/revision/geometry invariants and one actual drag; the direct image independently corroborates full visible controls and retained selection.',
    },
    'visualLimitations': limitations,
    'boundedVisualAcceptance': [
        'The exact photographed conceal, reveal, selection, Hide and fresh-Reveal checkpoints support their recorded visible-content findings.',
        'The native 2D and 3D captures show real native content, selection and concealment at the recorded checkpoints.',
        'Public native results, Standard returns, six Leave dialogs and four confirmed-Leave/cleanup Home captures were directly inspected.',
        'The 3D actual post-scroll capture shows complete Play, Challenge and Return to lobby controls while retaining selection.',
        'The immediate 2D NEXT_ROUND capture has only the narrower visual acceptance recorded in visualLimitations.',
    ],
    'scopeExclusions': [
        'Pixels do not establish engine identity, accepted actions, dormant counters or timing; those require the independently reviewed sanitized observations and named outcomes.',
        'No performance, first-frame latency, later smoothness, physical-device, store-signing, physical-network, full accessibility, package-inclusion or shipping-picker approval.',
    ],
}

pixel_data = (json.dumps(pixel, indent=2, ensure_ascii=False) + '\n').encode()
pixel_ref = record(PIXEL_PATH, pixel_data)
rollup = {
    'schemaVersion': 1,
    'reviewedAtUtc': now,
    'reviewer': REVIEWER,
    'runId': 34559902607,
    'attempt': 1,
    'headSha': '39405bb0fd6ba0214e70ed251aab1f9f571dc9aa',
    'nativeJobId': 103140623784,
    'disposition': 'Independent iOS review complete; current Debug arm64 Simulator named outcomes and exercised behavior approved within the stated evidence boundaries',
    'receipts': {
        'sourceReadiness': prior_records['native-review-readiness-v1.json'],
        'historicalSourceReconstruction': prior_records['prior-source-binding-check-reconstructed-v1.json'],
        'historicalSourceReconstructionProvenance': prior_records['prior-source-binding-reconstruction-provenance-v1.json'],
        'nativeJobLog': prior_records['native-log-independent-review-v1.json'],
        'dedicatedAuditorAndSchemaSource': prior_records['dedicated-auditor-source-independent-review-v1.json'],
        'sharedNativeJUnit': prior_records['shared-native-junit-independent-review-v1.json'],
        'dedicatedResultsAndSanitizedObservations': results_ref,
        'originalScreenshotReview': pixel_ref,
    },
    'verifiedScope': {
        'execution': 'Debug arm64 iOS Simulator; qualification source and selected effective settings reviewed',
        'namedXCTestCases': {'ordinaryPassed': 9, 'uikitLayoutPassed': 3, 'productionPassed': 2, 'eachNamedCaseOccursOnce': True},
        'sharedNativeJUnit': {'suites': 24, 'uniqueCases': 156, 'failures': 0, 'errors': 0, 'skipped': 0},
        'javaSwiftExchange': 'Both command directions exit 0 and close; frame sizes were reconciled with original results.',
        'sanitizedAttachments': {'sourceNamedObservations': 64, 'actualBodyScrollRecords': 1, 'opaqueJSONDecoded': 0},
        'originalPNGsDirectlyViewed': {'production': 41, 'ordinary': 10, 'total': 51},
        'productionBehavior': [
            'Standard five-card reveal, selection cap, Hide and fresh Reveal retain session/revision and do not eagerly create the native owner.',
            'Both native modes enter live, Ready, foreground and concealed; each case has two distinct real selection/Hide occurrences including a new practice.',
            'Each mode has exactly one accepted native PLAY_CARDS receipt bound to its measured pre-tap context, one intent increase and one fewer hand card.',
            'Return to Standard preserves the session, advances privacy and closes the renderer; actual accepted Standard action is NEXT_ROUND in both modes while retained native counters remain dormant.',
            'Each mode has three Leave dialogs; cancel retains the session, confirmed Leave returns Home, and new practice advances session/input generations while reusing the retained engine.',
            'Within each case, one native bootstrap and retained process/engine/controller/view/layer identity are established; dormant-close frame/iteration/draw/queue counters do not grow.',
            'The 3D new-practice body-scroll record proves one actual drag, unchanged input/privacy context and zero added intents, with all three enabled full-bounds controls. Challenge execution is not claimed.',
        ],
    },
    'materialVisualLimits': [
        'The immediate 2D accepted NEXT_ROUND screenshot still shows the previous result panel. Its sanitized receipt records accepted round 2; the later 2D Leave-cancel screenshot visibly shows ROUND 2. No atomic frame/state pairing or persistent rendering defect is inferred.',
        'Initial 3D frames clip Return to lobby; only the actual post-scroll checkpoint establishes full visible action bounds.',
        'Native 2D hand captures show only part of the horizontal strip at once. Ordinary Settings/result captures also have lower scroll content partly clipped.',
        'Production Standard/Home images contain a Q qualification marker and do not qualify as shipping screenshots.',
    ],
    'separateTimingInterpretation': {
        'owner': '/root/ios_fix',
        'receipt': timing_ref,
        'attribution': 'Separate-owner interpretation cited by exact supplied pin; this rollup does not duplicate or claim independent timing analysis.',
        'limitsFromOwner': 'Individual completed 18.764 s draw and 18.735 s iteration scopes are distinct from accumulated totals. First-frame timing remains unknown; unchanged maxima do not prove later smoothness. No performance or historical-fix acceptance and no code correction.',
    },
    'excludedAcceptance': [
        'Focused-production and shipping-picker selections were skipped; only actually executed named outcomes are approved.',
        'Package/PCK/native-binary joins belong to package_inclusion; canonical collection metadata belongs to ios_evidence.',
        'Process/gate/resource runtime evidence belongs to measurement_publish and resource_policy.',
        'No device, store-signing, physical-network, performance or exhaustive accessibility qualification.',
    ],
    'provenance': 'Historical source verification was reconstructed with explicit provenance and was not rerun. Current dedicated source/results/XML/screenshots were independently reviewed as pinned. No native reruns, new collection, ZIP/job-log rehashes or native source edits were performed for this sealing step.',
}
rollup_data = (json.dumps(rollup, indent=2, ensure_ascii=False) + '\n').encode()
existing_bytes = sum(p.stat().st_size for p in ROLE.rglob('*') if p.is_file())
assert existing_bytes + len(pixel_data) + len(rollup_data) <= 1024 * 1024

for path, data in ((PIXEL_PATH, pixel_data), (ROLLUP_PATH, rollup_data)):
    with path.open('xb') as handle:
        handle.write(data)
    path.chmod(0o444)
    assert path.read_bytes() == data
    print(json.dumps(record(path, data)))

print(json.dumps({
    'roleDirectoryBytes': existing_bytes + len(pixel_data) + len(rollup_data),
    'originalPngsDirectlyViewed': len(all_entries),
    'productionCaptureRefs': len(production_entries),
    'ordinaryCaptureRefs': len(ordinary_entries),
    'receiptConsistencyChecksPassed': True,
    'originalMediaRehashedBySealingScript': False,
}))
