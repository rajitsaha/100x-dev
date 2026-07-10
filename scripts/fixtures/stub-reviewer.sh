#!/usr/bin/env bash
# Test fixture: emits a scripted review + verdict. $1: APPROVED|CHANGES_REQUESTED
cat <<REVIEW
### Findings
1. [correctness] src/foo.py:10 — sample finding for tests
VERDICT: $1
REVIEW
