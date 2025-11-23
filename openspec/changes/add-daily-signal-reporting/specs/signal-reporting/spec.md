## ADDED Requirements
### Requirement: Daily Signal Summary Export
Signal generation SHALL produce a run summary when analyze or execute mode completes.

#### Scenario: Default markdown summary
- **WHEN** `generate_daily_signals` runs in analyze or execute mode
- **THEN** a summary file named `<portfolio>-<YYYYMMDD>-summary.md` is written to the summary output
  directory (default `results/daily_signals`)
- **AND** the file captures run timestamp, mode, strategy name, parameters used, stock list source, and
  data window

#### Scenario: JSON summary option
- **WHEN** the user sets `--summary-format json`
- **THEN** the tool writes a JSON summary containing the same fields as the markdown output

### Requirement: Summary Includes Portfolio Decisions
The summary SHALL detail the decisions taken so reviewers can audit trades.

#### Scenario: Orders and positions recorded
- **WHEN** orders are generated for the day
- **THEN** the summary lists each ticker with action (buy/sell/hold), intended size/weight, reference
  price, and applied filters or rationale when available
- **AND** it reports portfolio cash, equity value, and open positions before and after applying the
  orders

### Requirement: Configurable Summary Output
Users SHALL control where summaries are saved so automation can collect artifacts.

#### Scenario: Custom output directory respected
- **WHEN** the user provides `--summary-output <path>` and the directory does not exist
- **THEN** the tool creates the directory as needed and writes the summary file there without affecting
  other outputs
