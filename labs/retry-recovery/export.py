#!/usr/bin/env python3
"""Extract CSV timelines and compact comparisons from trusted local lab output."""
import csv
import gzip
import json
import sys
from pathlib import Path


def export(source, destination):
    opener = gzip.open if source.suffix == '.gz' else open
    with opener(source, 'rt') as handle:
        data = json.load(handle)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'summary.csv').open('w') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['rate', 'seed', 'fault', 'policy', 'arrivals', 'successes', 'terminal_failures',
                         'pending', 'attempts', 'attempts_per_original', 'recovery_confirmed_seconds'])
        for index, run in enumerate(data['runs']):
            # Filenames use enumeration, never strings supplied by the input JSON.
            (destination / f'timeline-{index:02d}.csv').write_text(run['timeline_csv'])
            t = run['totals']
            writer.writerow([run['rate'], run['seed'], run['fault'], run['policy'], t['arrivals'],
                             t.get('successes', 0), t.get('terminal_failures', 0),
                             run['original_statuses'].get('pending', 0), t['attempts'],
                             run['attempts_per_original'], run['recovery'].get('confirmed_after_seconds')])


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: export.py OBSERVATIONS.json[.gz] OUTPUT_DIRECTORY')
    export(Path(sys.argv[1]), Path(sys.argv[2]))
