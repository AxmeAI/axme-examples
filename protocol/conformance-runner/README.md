# Protocol Example: Conformance Runner

Goal: run AXP conformance tests against your own implementation.

## Prerequisites

- an AXP-compatible endpoint implementation
- access to `axme-conformance` repository

## Typical flow

1. Start your implementation endpoint (local/staging)
2. Configure conformance target URL and auth mode
3. Execute conformance suite
4. Review pass/fail matrix and fix mismatches

Helper in this folder:

- `run_conformance.sh` - minimal command scaffold for target URL

## Why this matters

Conformance validates that custom implementations stay protocol-compatible even when not using AXME Cloud runtime.
