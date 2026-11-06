"""Validate a review queue or freeze agreed labels for offline retrieval evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cra2.public_evidence import load_public_evidence
from scripts.evaluate_retrieval import validate_cases


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def review(packet):
    if not isinstance(packet, dict) or set(packet) != {'schema_version', 'origin', 'cases'}:
        raise ValueError('Invalid review packet')
    if type(packet['schema_version']) is not int or packet['schema_version'] != 1 or packet['origin'] != 'assistant_authored_synthetic':
        raise ValueError('Unsupported review packet provenance')
    if not isinstance(packet['cases'], list) or not 1 <= len(packet['cases']) <= 256:
        raise ValueError('Invalid review case count')
    rows, states = [], []
    known = {r['id'] for r in load_public_evidence()}
    for case in packet['cases']:
        if not isinstance(case, dict) or set(case) != {'id', 'split', 'service', 'query', 'rationale', 'reviews'}:
            raise ValueError('Invalid review case fields')
        reviews = case['reviews']
        if not isinstance(reviews, list) or len(reviews) > 2:
            raise ValueError('Expected at most two reviews')
        reviewers, labels = set(), []
        for entry in reviews:
            if not isinstance(entry, dict) or set(entry) != {'reviewer', 'source_ids', 'reason'}:
                raise ValueError('Invalid review fields')
            for field in ('reviewer', 'reason'):
                if not isinstance(entry[field], str) or not entry[field].strip() or len(entry[field]) > 2000:
                    raise ValueError('Invalid reviewer or reason')
            identity = entry['reviewer'].strip().casefold()
            if identity in reviewers:
                raise ValueError('Two distinct reviewers are required')
            reviewers.add(identity)
            label = entry['source_ids']
            if label is not None and (not isinstance(label, list) or len(label) > 1 or any(not isinstance(x, str) or x not in known for x in label)):
                raise ValueError('Review needs null, an empty list, or one known source')
            labels.append(label)
        agreed = len(labels) == 2 and None not in labels and labels[0] == labels[1]
        state = 'agreed' if agreed else 'pending' if len(labels) < 2 else 'ambiguous' if None in labels else 'conflict'
        states.append({'id': case['id'], 'state': state})
        rows.append({**{k: v for k, v in case.items() if k != 'reviews'}, 'expected_source_ids': labels[0] if agreed else []})
    # Checks query identity/service/schema and split leakage among agreed labels.
    validate_cases({'schema_version': 1, 'cases': rows})
    return rows, states


def freeze(packet):
    cases, states = review(packet)
    if any(s['state'] != 'agreed' for s in states):
        raise ValueError('Pending, ambiguous or conflicting labels cannot be frozen')
    return {'schema_version': 1, 'packet': packet, 'packet_sha256': digest(packet),
            'corpus_sha256': digest(load_public_evidence()), 'cases': cases}


def load_frozen_bundle(bundle):
    if (not isinstance(bundle, dict) or type(bundle.get('schema_version')) is not int
            or 'packet' not in bundle or bundle != freeze(bundle['packet'])):
        raise ValueError('Frozen review bundle changed or corpus is stale')
    return bundle['cases']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--freeze', type=Path, help='Create a new frozen bundle; never overwrite an existing file')
    args = parser.parse_args()
    packet = json.loads(args.packet.read_bytes())
    _, states = review(packet)
    if args.freeze:
        bundle = freeze(packet)
        with args.freeze.open('x') as stream:
            stream.write(json.dumps(bundle, indent=2) + '\n')
    print(json.dumps({'cases': len(states), 'states': states}, indent=2))


if __name__ == '__main__':
    main()
