# Frozen retry pilot plan

Before execution: use exactly config.json, with all 54 combinations retained.
No post-result tuning or claim of metastability is an acceptance condition.
The configured arrival rates are 20%, 60%, and 90% of normal single-server
capacity; 4/sec is the low-load control. Every rate also has a no-fault control.
Seeds 11, 29, 47 determine Poisson arrival schedules shared across policies and
fault modes. Retry jitter is independently derived per original/attempt.

Single FIFO server, fixed service time selected at service start. A timeout
abandons the client's attempt but never cancels queued/running server work.
Late completion cannot rescue a timed-out original. Retries enter the same FIFO;
there is no deduplication. These are modeling assumptions, not measured service
behavior. Arrivals before 180 seconds are admitted; simulation ends at 180,
retaining pending originals and unfinished work rather than silently draining.

Original requests terminate on a timely response, total deadline, exhausted
attempts, queue rejection, or denied retry token. The process-wide token bucket
starts full, gates retries only, and denial terminates that original. This is
admission control, not a model of any specific SDK. The queue limit counts waiting
work, excluding the single running attempt. Attempt cap stops the run and records
censoring. No extracted code or external services run.

Recovery uses original successes per 1-second completion window. Baseline is
the mean of windows [20,60). Starting at fault removal (80), require ten consecutive
windows at least 95% of baseline. Report the *end* of the confirming tenth window
minus 80, and its start separately. No qualification by cutoff is right-censoring,
not proof of metastability. Poisson noise can prevent qualification. CSV preserves
successes from pre-trigger, trigger, and post-trigger arrivals separately, plus
arrivals, attempts, terminal failures, queue samples, and remaining originals.
Latency includes terminal failures and separately retained pending ages.

Resources: one CPU, 512 MiB container ceiling, 100,000 attempts/run, 30 minutes
wall-clock suite ceiling. Docker has no network, root privileges, host mounts,
capabilities, or writable root. Outputs leave through stdout. Tiny original
stdlib code; no upstream implementation is copied or executed. Results may
justify no new article. Svalinn and multi-resource controls remain out of scope.
