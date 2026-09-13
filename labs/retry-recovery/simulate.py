#!/usr/bin/env python3
"""Fixed, synthetic discrete-event retry model; no service benchmark or replication."""
import csv
import hashlib
import heapq
import io
import itertools
import json
import os
import platform
import random
import sys
import time
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).parent
PRIORITY = {'complete': 0, 'deadline': 1, 'timeout': 2, 'retry': 3, 'arrival': 4, 'sample': 5}


def arrivals(rate, seed, duration):
    rng = random.Random(seed)
    now = 0.0
    schedule = []
    while True:
        now += rng.expovariate(rate)
        if now >= duration:
            return schedule
        schedule.append(now)


def recovery(windows, config):
    baseline = sum(w['successes'] for w in windows
                   if config['baseline_start_seconds'] <= w['window_start'] < config['trigger_start_seconds'])
    baseline /= (config['trigger_start_seconds'] - config['baseline_start_seconds']) / config['window_seconds']
    streak = 0
    threshold = config['recovery_fraction'] * baseline
    for w in windows:
        if w['window_start'] < config['trigger_end_seconds']:
            continue
        streak = streak + 1 if baseline > 0 and w['successes'] >= threshold else 0
        if streak == config['recovery_consecutive_windows']:
            end = w['window_start'] + config['window_seconds']
            return {'baseline_successes_per_window': baseline, 'threshold': threshold,
                    'confirmed_after_seconds': end - config['trigger_end_seconds'],
                    'qualifying_start': end - streak * config['window_seconds'], 'censored': False}
    return {'baseline_successes_per_window': baseline, 'threshold': threshold,
            'confirmed_after_seconds': None, 'qualifying_start': None, 'censored': True}


def simulate(config, rate, seed, fault, policy, arrival_override=None):
    if policy not in ('none', 'jitter', 'budget'):
        raise ValueError('unknown policy')
    c = config
    duration = c['duration_seconds']
    schedule = arrivals(rate, seed, duration) if arrival_override is None else arrival_override
    events, serial = [], itertools.count()
    def push(now, kind, value):
        heapq.heappush(events, (now, PRIORITY[kind], next(serial), kind, value))
    for rid, when in enumerate(schedule):
        push(when, 'arrival', rid)
    for end in range(c['window_seconds'], duration + 1, c['window_seconds']):
        push(end, 'sample', None)
    originals, attempts, queue = {}, {}, deque()
    totals = Counter()
    windows = [Counter(window_start=n) for n in range(0, duration, c['window_seconds'])]
    busy = None
    tokens = c['retry_token_capacity']
    token_updated = 0.0
    stopped = None
    now = 0.0
    def add(key, amount=1):
        totals[key] += amount
        index = min(int(now // c['window_seconds']), len(windows) - 1)
        windows[index][key] += amount
    def terminate(rid, reason):
        original = originals[rid]
        if original['status'] != 'pending':
            return
        original['status'] = reason
        original['terminal_at'] = now
        add('successes' if reason == 'success' else 'terminal_failures')
        if reason != 'success':
            add(reason)
        else:
            phase = ('pre_trigger' if original['arrived'] < c['trigger_start_seconds'] else
                     'trigger' if original['arrived'] < c['trigger_end_seconds'] else 'post_trigger')
            add('successes_' + phase)
    def start(aid):
        nonlocal busy
        busy = aid
        attempts[aid]['started'] = now
        slow = fault and c['trigger_start_seconds'] <= now < c['trigger_end_seconds']
        push(now + c['slow_service_seconds' if slow else 'normal_service_seconds'], 'complete', aid)
    def launch(rid):
        nonlocal stopped
        if totals['attempts'] >= c['attempt_cap']:
            stopped = 'attempt_cap'
            return
        original = originals[rid]
        original['attempts'] += 1
        add('attempts')
        if busy is not None and len(queue) >= c['queue_capacity']:
            add('rejected_attempts')
            if original['attempts'] == 1:
                add('dropped_arrivals')
            terminate(rid, 'queue_rejected')
            return
        aid = len(attempts)
        attempts[aid] = {'original': rid, 'sent': now, 'timed_out': False}
        add('admitted_attempts')
        push(now + c['attempt_timeout_seconds'], 'timeout', aid)
        if busy is None:
            start(aid)
        else:
            queue.append(aid)
    while events:
        when, _, _, kind, value = heapq.heappop(events)
        if when > duration:
            break
        now = when
        if kind == 'arrival':
            originals[value] = {'arrived': now, 'attempts': 0, 'status': 'pending'}
            add('arrivals')
            push(now + c['original_deadline_seconds'], 'deadline', value)
            launch(value)
        elif kind == 'deadline':
            terminate(value, 'deadline_expired')
        elif kind == 'retry':
            original = originals[value]
            if original['status'] == 'pending':
                if policy == 'budget':
                    tokens = min(c['retry_token_capacity'], tokens + (now - token_updated) * c['retry_tokens_per_second'])
                    token_updated = now
                    if tokens < 1:
                        terminate(value, 'budget_denied')
                        continue
                    tokens -= 1
                launch(value)
        elif kind == 'timeout':
            attempt = attempts[value]
            if 'completed' in attempt:
                continue
            attempt['timed_out'] = True
            add('attempt_timeouts')
            rid = attempt['original']
            original = originals[rid]
            if original['status'] != 'pending':
                continue
            if policy == 'none' or original['attempts'] >= c['max_attempts_per_original']:
                terminate(rid, 'attempts_exhausted')
            else:
                limit = min(c['backoff_cap_seconds'], c['backoff_base_seconds'] * 2 ** (original['attempts'] - 1))
                jitter = random.Random(f'{seed}:{rid}:{original["attempts"]}').uniform(0, limit)
                push(now + jitter, 'retry', rid)
        elif kind == 'complete':
            attempt = attempts[value]
            attempt['completed'] = now
            add('completed_attempts')
            if not attempt['timed_out'] and originals[attempt['original']]['status'] == 'pending':
                terminate(attempt['original'], 'success')
            else:
                add('unused_completions')
            busy = None
            if queue:
                start(queue.popleft())
        elif kind == 'sample':
            window = windows[int(now // c['window_seconds']) - 1]
            window['queue_depth_at_end'] = len(queue)
            window['in_service_at_end'] = int(busy is not None)
            window['pending_originals_at_end'] = sum(o['status'] == 'pending' for o in originals.values())
        if stopped:
            break
    pending = [now - o['arrived'] for o in originals.values() if o['status'] == 'pending']
    statuses = Counter(o['status'] for o in originals.values())
    terminal_latencies = [{'original': rid, 'status': o['status'], 'seconds': o['terminal_at'] - o['arrived']}
                          for rid, o in originals.items() if o['status'] != 'pending']
    # Zeros are explicit in every CSV window. Truncated runs expose only elapsed windows.
    columns = ('window_start', 'arrivals', 'attempts', 'admitted_attempts', 'successes',
               'successes_pre_trigger', 'successes_trigger', 'successes_post_trigger',
               'terminal_failures', 'dropped_arrivals', 'attempt_timeouts', 'completed_attempts',
               'unused_completions', 'queue_depth_at_end', 'in_service_at_end', 'pending_originals_at_end')
    rows = [{key: w[key] for key in columns} for w in windows if w['window_start'] + c['window_seconds'] <= now]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return {'rate': rate, 'seed': seed, 'fault': fault, 'policy': policy,
            'arrival_schedule_sha256': hashlib.sha256(json.dumps(schedule).encode()).hexdigest(),
            'scheduled_arrivals': len(schedule), 'observed_until': now, 'stop_reason': stopped or 'observation_cutoff',
            'totals': dict(totals), 'original_statuses': dict(statuses),
            'attempts_per_original': totals['attempts'] / totals['arrivals'] if totals['arrivals'] else None,
            'unfinished_server_work': len(queue) + int(busy is not None),
            'pending_original_ages': pending, 'terminal_latencies': terminal_latencies,
            'recovery': recovery(rows, c) if not stopped else {'censored': True, 'reason': stopped},
            'timeline_csv': out.getvalue()}


def main():
    started = time.monotonic()
    raw = (ROOT / 'config.json').read_bytes()
    config = json.loads(raw)
    result = {'kind': 'synthetic-discrete-event-simulation', 'config': config,
              'config_sha256': hashlib.sha256(raw).hexdigest(),
              'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                              'image_id': os.getenv('LAB_IMAGE_ID', 'unrecorded'),
                              'revision': os.getenv('LAB_REVISION', 'unrecorded'),
                              'dirty': os.getenv('LAB_DIRTY', 'unrecorded')}, 'runs': []}
    for seed, rate, fault, policy in itertools.product(config['seeds'], config['arrival_rates_per_second'],
                                                     config['fault_modes'], config['policies']):
        if time.monotonic() - started >= config['wall_clock_budget_seconds']:
            result['stop_reason'] = 'wall_clock_budget'
            break
        result['runs'].append(simulate(config, rate, seed, fault, policy))
    result['elapsed_wall_seconds'] = time.monotonic() - started
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
