import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
PLAN = json.loads((BASE / 'review-plan.json').read_text())

def record(index, state, note, private_faces):
    capture = PLAN['captures'][index]
    assert capture['reviewStatus'] == 'planned_direct_original'
    ledger = BASE / 'direct-observations.jsonl'
    previous = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    assert not any(x['captureIndex'] == index for x in previous)
    item = {
        'captureIndex': index, 'recordedUtc': datetime.now(timezone.utc).isoformat(),
        'timestampScope': 'Receipt written after the direct original pixel view; not an original capture timestamp.',
        'reviewer': '/root/review_design', 'method': 'direct_original_full_size_view_image',
        'path': capture['canonicalOriginal']['path'], 'physicalAlias': capture['original']['path'],
        'sha256': capture['original']['sha256'], 'bytes': capture['original']['bytes'],
        'dimensions': [capture['widthPx'], capture['heightPx']],
        'originalAttachment': capture['exportMetadata'], 'testIdentifier': capture['testIdentifier'],
        'caseOutcome': capture['caseOutcome'], 'label': capture['humanLabel'],
        'state': state, 'observations': note, 'privateCardFacesVisible': private_faces,
        'scope': 'Pixel observation only; original result and separately acquired cached lastDocument remain distinct.'
    }
    with ledger.open('a') as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(index, item['sha256'], state)
