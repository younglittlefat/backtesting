## ADDED Requirements

### Requirement: Dynamic rotation schedule portfolio backtest
The system SHALL support portfolio backtests that refresh the tradable pool on configured rotation dates using a precomputed schedule while preserving existing scoring, clustering, sizing, and stop logic.

#### Scenario: Load and enforce rotation schedule
- **GIVEN** a rotation schedule JSON that includes `metadata.rotation_period` and `schedule` keyed by `YYYY-MM-DD`
- **WHEN** a dynamic portfolio backtest starts
- **THEN** the runner SHALL load the schedule, reject missing/non-existent files, and error if the backtest start date precedes the first rotation date.

#### Scenario: Rotate pool on schedule dates
- **GIVEN** a running backtest with an active pool from the latest schedule date
- **WHEN** the current decision date matches a rotation date in the schedule
- **THEN** the runner SHALL replace the tradable pool with the symbols listed for that date, force-sell holdings not in the new pool (reason `rotation_excluded` or equivalent), and continue rebalancing with buffer and cluster constraints.

#### Scenario: Handle gaps without look-ahead
- **GIVEN** a gap in `schedule` (no entry for a trading date range)
- **WHEN** the backtest processes a date without a schedule entry
- **THEN** the runner SHALL carry forward the most recent past pool, SHALL NOT peek at future rotation dates, and MUST error if no past pool exists (e.g., before first rotation).

#### Scenario: Use price/indicator history only up to decision date
- **GIVEN** signals, scores, clusters, and risk checks computed during a rotation window
- **WHEN** the runner evaluates eligibility and sizing for a decision date
- **THEN** it SHALL use only data with index ≤ the decision date for each symbol, preventing look-ahead while still allowing pre-loaded history for performance.

### Requirement: Dynamic mode configuration and safety
The system SHALL provide explicit configuration to enable dynamic rotation mode and guard against misconfiguration with the existing static pool flow.

#### Scenario: Explicit dynamic mode and required schedule path
- **GIVEN** config with `rotation.enabled=true`
- **WHEN** the runner initializes
- **THEN** it SHALL require `rotation.schedule_path` to exist, SHALL error if both `rotation.enabled` and `universe.pool_file/pool_list` are provided, and SHALL read optional `rotation.period_days`/`rotation.pool_size` defaults for logging only.

#### Scenario: Static mode backward compatibility
- **GIVEN** config with `rotation.enabled=false` (or absent)
- **WHEN** the runner runs
- **THEN** it SHALL execute the existing static pool backtest behavior without reading rotation schedules and SHALL preserve current CLI/config compatibility.
