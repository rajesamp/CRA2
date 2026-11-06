"""Exchange individual judgments without exposing another reviewer's labels."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from cra2.public_evidence import load_public_evidence
from scripts.review_retrieval import digest, review


def worksheet(packet):
    review(packet)
    # Bind the complete scenario definition, excluding mutable review progress.
    definitions = [{k: v for k, v in row.items() if k != 'reviews'} for row in packet['cases']]
    return {'schema_version': 1, 'queue_sha256': digest(definitions),
            'corpus_sha256': digest(load_public_evidence()),
            'cases': [{k: row[k] for k in ('id', 'service', 'query')} for row in definitions],
            'reviewer': '', 'judgments': []}


def submit(packet, sheet):
    template = worksheet(packet)
    if not isinstance(sheet, dict) or set(sheet) != set(template) or type(sheet['schema_version']) is not int:
        raise ValueError('Invalid reviewer worksheet')
    for field in ('schema_version', 'queue_sha256', 'corpus_sha256', 'cases'):
        if sheet[field] != template[field]:
            raise ValueError('Worksheet is stale or its scenario definitions changed')
    reviewer = sheet['reviewer']
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 2000:
        raise ValueError('A reviewer identifier is required')
    judgments = sheet['judgments']
    if not isinstance(judgments, list) or not 1 <= len(judgments) <= len(template['cases']):
        raise ValueError('Supply at least one judgment')
    updated = deepcopy(packet)
    rows = {row['id']: row for row in updated['cases']}
    seen = set()
    for judgment in judgments:
        if not isinstance(judgment, dict) or set(judgment) != {'case_id', 'source_ids', 'reason'}:
            raise ValueError('Invalid judgment fields')
        case_id = judgment['case_id']
        if not isinstance(case_id, str) or case_id not in rows or case_id in seen:
            raise ValueError('Unknown or duplicate case')
        seen.add(case_id)
        row = rows[case_id]
        if any(r['reviewer'].strip().casefold() == reviewer.strip().casefold() for r in row['reviews']):
            raise ValueError('Existing reviewer judgment cannot be overwritten by import')
        row['reviews'].append({'reviewer': reviewer.strip(), 'source_ids': judgment['source_ids'],
                               'reason': judgment['reason']})
    review(updated)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--submission', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_bytes())
    result = submit(packet, json.loads(args.submission.read_bytes())) if args.submission else worksheet(packet)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print('Created reviewed queue copy.' if args.submission else 'Created individual reviewer worksheet.')


if __name__ == '__main__':
    main()
