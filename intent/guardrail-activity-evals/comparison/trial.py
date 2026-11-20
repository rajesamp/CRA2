import asyncio
import importlib.metadata
import json
import math
import os
from pathlib import Path
import socket
import sys

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'
attempts = []
def no_network(event, args):
    if event == 'socket.getaddrinfo' or event in {'socket.connect', 'socket.sendto'} and args[0].family in {socket.AF_INET, socket.AF_INET6}:
        attempts.append(event)
        raise RuntimeError('offline network boundary')
sys.addaudithook(no_network)
cases = [
    ('perfect', ['a','b'], ['a','b']),
    ('partial', ['a','x'], ['a','b']),
    ('miss', ['x','y'], ['a','b']),
    ('empty_retrieval', [], ['a','b']),
    ('duplicate', ['a','a'], ['a','b']),
    ('empty_reference', ['a'], []),
]
framework = sys.argv[1]
rows = []
if framework == 'ragas':
    from ragas import SingleTurnSample
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall
    async def score(retrieved, reference):
        sample = SingleTurnSample(retrieved_context_ids=retrieved, reference_context_ids=reference)
        return [await metric.single_turn_ascore(sample) for metric in (IDBasedContextPrecision(), IDBasedContextRecall())]
    for name, retrieved, reference in cases:
        try: values = asyncio.run(score(retrieved, reference))
        except Exception as e: values = [type(e).__name__]
        rows.append({'case': name, 'precision_recall': values})
else:
    from trulens.feedback import GroundTruthAgreement
    from trulens.feedback.llm_provider import LLMProvider
    class ForbiddenProvider(LLMProvider):
        def _create_chat_completion(self, *args, **kwargs):
            attempts.append('provider_call')
            raise RuntimeError('provider forbidden')
    provider = ForbiddenProvider(model_engine='offline-forbidden')
    for name, retrieved, reference in cases:
        ground = [{'query':name,'expected_chunks':[{'text':v,'expect_score':1} for v in reference]}]
        metric = GroundTruthAgreement(ground, provider=provider)
        try: values = [metric.precision_at_k(name, retrieved), metric.recall_at_k(name, retrieved)]
        except Exception as e: values = [type(e).__name__]
        rows.append({'case': name, 'precision_recall': values})
for row in rows:
    row['precision_recall'] = [None if isinstance(x,float) and not math.isfinite(x) else x for x in row['precision_recall']]
report = {'framework':framework, 'version': importlib.metadata.version('ragas' if framework=='ragas' else 'trulens-feedback'),
          'network_and_provider_attempts':attempts, 'cases':rows,
          'environment_distributions':len(list(importlib.metadata.distributions())),
          'limitations':'Synthetic ID equality only; no answer-quality or robustness comparison.'}
Path(__file__).with_name(framework+'-result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
