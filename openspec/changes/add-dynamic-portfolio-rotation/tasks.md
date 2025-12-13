## 1. Specification
- [x] 1.1 Draft spec delta for `portfolio-dynamic-filtering` with rotation schedule + rebalance requirements
- [x] 1.2 Validate change with `openspec validate add-dynamic-portfolio-rotation --strict`

## 2. Implementation
- [x] 2.1 Implement `DynamicPoolPortfolioRunner` (rotation schedule loading, rotation-day pool refresh, incremental rebalance)
- [x] 2.2 Extend config/CLI to support `rotation.enabled`, `rotation.schedule_path`, `rotation.period_days`, `rotation.pool_size`, and guard mutual exclusivity with static pools
- [x] 2.3 Add fixtures and unit tests (schedule loading, rotation behavior, backward compatibility with static runner)

## 3. Verification
- [x] 3.1 Run targeted pytest for new dynamic runner/tests
- [x] 3.2 Document usage and confirm acceptance criteria from requirement doc
