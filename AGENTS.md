# Agent instructions

This file is the harness-neutral source of project instructions. Apply it regardless of model or editor.

- This repository holds bounded research artifacts; editorial drafts belong in the website repository.
- Never claim an experiment ran without retaining commands, environment and raw observations.
- Separate observed behavior, source findings and inference. Negative results remain evidence.
- Use deterministic synthetic data. Do not add untrusted archive inputs, live targets, paid APIs,
  secrets, network services, extracted-content execution or privileged runtime requirements.
- Keep each lab's hypothesis, limits, provenance and interpretation beside its code.
- Pin dependencies and images. Record changes to fixtures and rerun meaningful checks.
- Run `./scripts/lab.sh test` and `./scripts/lab.sh run > /tmp/zip-review.json` for ZIP code changes.
- Raw results belong in `results/` (ignored) or a deliberately reviewed `docs/evidence/` record.
- Do not copy research code or figures without checking its license and preserving attribution.
- Review accuracy, safety, reproducibility and scope before publication. Consensus is not evidence
  of a factual claim; retain dissent and verify challenged observations independently.
