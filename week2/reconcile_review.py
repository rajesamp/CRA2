"""Repair C4 receipts for one review using the operator's selected gcloud account."""
import argparse
import os
import subprocess

from week2.cloud_storage import CloudAudit, CloudPreferences, StorageClient, StorageSettings
from week2.preference_journal import journal_name


class OperatorClient(StorageClient):
    def _headers(self):
        output = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True,
                                timeout=20, check=True)
        return {'Authorization': 'Bearer ' + output.stdout.decode('ascii').strip()}


def reconcile(settings, client, review):
    row, _ = client.read(settings.state_bucket, journal_name(review))
    if row is None:
        return 'unknown_review'
    memory = CloudPreferences(settings.state_bucket, client, CloudAudit(settings, client), row['scope'])
    memory.audit.ensure()
    return memory.journal.reconcile(review, client)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review_id')
    args = parser.parse_args()
    try:
        settings = StorageSettings(os.environ['CRA2_STATE_BUCKET'], os.environ['CRA2_AUDIT_BUCKET'])
        status = reconcile(settings, OperatorClient(), args.review_id)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        status = 'confirmation_incomplete'
    print(status)
    return 0 if status in {'committed', 'failed'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
