"""Offline, source-separated retrieval evaluation; never calls an LLM."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cra2.advisor import CATALOG
from cra2.public_evidence import load_public_evidence, validate_public_hit

ROOT = Path(__file__).resolve().parents[1]


def load_cases(path):
    data = json.loads(Path(path).read_text())
    if set(data) != {'schema_version', 'cases'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Invalid evaluation schema')
    cases = data['cases']
    if not isinstance(cases, list) or not cases:
        raise ValueError('Evaluation needs cases')
    sources = {r['id']: r['source_url'] for r in load_public_evidence()}
    seen, queries, partitions = set(), set(), {}
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'split', 'service', 'query', 'expected_source_ids', 'rationale'}:
            raise ValueError('Invalid case fields')
        for key in ('id', 'query', 'rationale'):
            if not isinstance(case[key], str) or not case[key].strip() or len(case[key]) > 5000:
                raise ValueError('Invalid case text')
        if case['id'] in seen or case['query'].strip().lower() in queries:
            raise ValueError('Duplicate case or query')
        seen.add(case['id'])
        queries.add(case['query'].strip().lower())
        if case['split'] not in ('development', 'evaluation') or case['service'] not in CATALOG:
            raise ValueError('Invalid split or service')
        expected = case['expected_source_ids']
        if not isinstance(expected, list) or len(expected) > 1 or any(not isinstance(x, str) or x not in sources for x in expected):
            raise ValueError('Each case needs zero or one known target source')
        for source in expected:
            url = sources[source]
            if url in partitions and partitions[url] != case['split']:
                raise ValueError('Source incident leaks across splits')
            partitions[url] = case['split']
    if {c['split'] for c in cases} != {'development', 'evaluation'}:
        raise ValueError('Both source partitions are required')
    return cases


def evaluate(cases, search):
    rows = []
    for case in cases:
        hits = search(case['query'], service=case['service'])
        if any(h['doc_id'].startswith('public-') and h['source_dataset'] != 'public_corporate' for h in hits):
            raise ValueError('Public source provenance stripped')
        external = [h for h in hits if h['source_dataset'] == 'public_corporate']
        if len(hits) > 3 or len(external) > 1:
            raise ValueError('Retrieval result cap violated')
        for hit in external:
            validate_public_hit(hit)
        if any(h['service'] not in (None, case['service']) for h in hits if h not in external):
            raise ValueError('Local service scope violated')
        target = case['expected_source_ids']
        rank = next((i for i, h in enumerate(hits, 1) if h['doc_id'] in target), None)
        rows.append({'id': case['id'], 'split': case['split'], 'query': case['query'],
                     'expected_source_ids': target, 'target_rank': rank,
                     'negative_pass': not external if not target else None,
                     'hits': [{k: h[k] for k in ('chunk_id', 'doc_id', 'service', 'source', 'source_dataset', 'score')} for h in hits]})
    metrics = {}
    for split in ('development', 'evaluation'):
        positives = [r for r in rows if r['split'] == split and r['expected_source_ids']]
        negatives = [r for r in rows if r['split'] == split and not r['expected_source_ids']]
        metrics[split] = {
            'positive_cases': len(positives), 'target_hits_at_3': sum(r['target_rank'] is not None for r in positives),
            'target_hit_rate_at_3': sum(r['target_rank'] is not None for r in positives) / len(positives) if positives else None,
            'mean_reciprocal_rank_at_3': sum(1 / r['target_rank'] if r['target_rank'] else 0 for r in positives) / len(positives) if positives else None,
            'negative_cases': len(negatives), 'negative_passes': sum(r['negative_pass'] for r in negatives),
        }
    return {'metrics': metrics, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'evals/retrieval-cases.json')
    parser.add_argument('--index', type=Path, default=ROOT / 'week1/.cache/index.sqlite3')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.cases)
    from week1 import retrieval
    result = evaluate(cases, lambda query, **kw: retrieval.search(query, args.index, **kw))
    # search validates corpus/model fingerprints against the current index.
    connection, metadata = retrieval._open_index(args.index)
    connection.close()
    result.update(schema_version=1, cases_sha256=hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                  corpus_digest=metadata['corpus_digest'], encoder_fingerprint=metadata['encoder_fingerprint'],
                  provider_requests=0,
                  scope='Small assistant-authored source-separated scenarios; not blind evaluation, exhaustive relevance labels, or production accuracy.')
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['metrics'], indent=2))


if __name__ == '__main__':
    main()
