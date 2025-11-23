## 1. Implementation
- [ ] 1.1 Add CLI options (`--summary-output`, `--summary-format`) and plumb through the signal runner
- [ ] 1.2 Generate summary content with metadata, positions before/after, orders, and risk flags; support
      Markdown and JSON
- [ ] 1.3 Save files under `results/daily_signals` with date-stamped names; ensure directories are created
- [ ] 1.4 Add tests/fixtures for summary export and update docs/README usage

## 2. Validation
- [ ] 2.1 Run targeted pytest for summary writer and any impacted modules
- [ ] 2.2 Run `openspec validate add-daily-signal-reporting --strict`
