"""Loopback-only reviewer workspace. No model, retrieval ranking or automatic import."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import gradio as gr

from cra2.public_evidence import load_public_evidence
from scripts.evaluate_retrieval import ROOT
from scripts.review_exchange import submit, worksheet

UNCERTAIN = 'Unsure / insufficient detail'
NONE = 'No justified external analogue'
MATCH = 'One relevant source'


def save_judgment(packet, sheet, reviewer, case_id, decision, source_id, reason):
    candidate = deepcopy(sheet)
    if candidate['judgments'] and candidate['reviewer'].strip().casefold() != reviewer.strip().casefold():
        raise ValueError('Start a new workspace to change reviewer after saving judgments')
    if decision not in (UNCERTAIN, NONE, MATCH):
        raise ValueError('Select a judgment')
    known = {r['id'] for r in load_public_evidence()}
    if decision == MATCH and source_id not in known:
        raise ValueError('Select a source')
    candidate['reviewer'] = reviewer
    candidate['judgments'] = [j for j in candidate['judgments'] if j['case_id'] != case_id]
    candidate['judgments'].append({'case_id': case_id, 'source_ids': None if decision == UNCERTAIN else [] if decision == NONE else [source_id], 'reason': reason})
    # Validate against the original queue before exporting this individual draft.
    submit(packet, candidate)
    return candidate


def build_app(packet):
    template = worksheet(packet)
    cases = {c['id']: c for c in template['cases']}
    sources = {r['id']: r for r in load_public_evidence()}
    first = next(iter(cases))

    def show_case(case_id, sheet):
        case = cases[case_id]
        previous = next((j for j in sheet['judgments'] if j['case_id'] == case_id), None)
        label = previous['source_ids'] if previous else None
        return (case['service'], case['query'], UNCERTAIN if label is None else NONE if not label else MATCH,
                label[0] if label else None, previous['reason'] if previous else '')

    def show_source(source_id):
        source = sources.get(source_id)
        if not source:
            return ''
        return '\n\n'.join([source['source_url'], source['reported_facts'],
                             'Recovery: ' + (source['reported_recovery'] or 'Unverified'),
                             'Caveats: ' + source['caveats']])

    def save(sheet, reviewer, case_id, decision, source_id, reason):
        try:
            updated = save_judgment(packet, sheet, reviewer, case_id, decision, source_id, reason)
        except (ValueError, TypeError, KeyError, AttributeError):
            return sheet, 'Not saved. Check reviewer, source and reason; existing imported judgments cannot be overwritten.', json.dumps(sheet, indent=2) if sheet.get('judgments') else ''
        return updated, f"Saved {len(updated['judgments'])} of {len(cases)} judgments in this session.", json.dumps(updated, indent=2)

    with gr.Blocks(title='CRA2 Evidence Review', analytics_enabled=False) as demo:
        gr.Markdown('# CRA2 Evidence Review\nReview synthetic change scenarios against external corporate evidence. '
                    'Your judgments do not approve deployments or change CRA2 risk rules. '
                    'Other reviewers’ judgments and model rankings are not shown.')
        state = gr.State(value=deepcopy(template))
        reviewer = gr.Textbox(label='Your reviewer identifier')
        case_id = gr.Dropdown(choices=list(cases), value=first, label='Scenario')
        service = gr.Textbox(value=cases[first]['service'], label='CRA2 service', interactive=False)
        query = gr.Textbox(value=cases[first]['query'], label='Proposed change', interactive=False)
        decision = gr.Radio([UNCERTAIN, NONE, MATCH], value=UNCERTAIN, label='Your judgment')
        source = gr.Dropdown(choices=[(r['company'] + ' · ' + r['original_service'] + ' · ' + str(r['incident_date'] or r['planned_change_date']), r['id']) for r in sources.values()], label='Browse a company source')
        details = gr.Textbox(label='Source URL, reported facts and caveats', interactive=False, lines=9)
        reason = gr.Textbox(label='Explain your judgment', lines=3)
        button = gr.Button('Save judgment to worksheet')
        status = gr.Textbox(label='Progress', interactive=False)
        exported = gr.Textbox(label='Submission JSON — copy and save for the coordinator', interactive=False, lines=8)
        gr.Markdown('Drafts stay in this browser session’s server memory and are lost on restart. '
                    'Copy the submission before closing. Reviewer identifiers are self-reported; this is not authentication. '
                    'Use separate sessions for independent reviewers.')
        case_id.change(show_case, [case_id, state], [service, query, decision, source, reason])
        source.change(show_source, source, details)
        button.click(save, [state, reviewer, case_id, decision, source, reason], [state, status, exported])
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, default=ROOT / 'evals/retrieval-review-queue.json')
    parser.add_argument('--port', type=int, default=7863)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_bytes())
    build_app(packet).launch(server_name='127.0.0.1', server_port=args.port, share=False)


if __name__ == '__main__':
    main()
