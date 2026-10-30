# RELIABILITY_CONTRACT.md
# ADAI Reliability Contract

This project now includes the first durable reliability layer for automation tasks.

What is included:
- Automation task state model and lease acquisition helpers.
- Failure classification for common provider, network, and browser errors.
- Centralized retry policy with bounded delays.
- Recovery knowledge scaffolding with verified and proposed strategies.
- A minimal automation API for creating, leasing, canceling, and classifying tasks.

Key invariants captured in code:
1. Task execution is treated as a persisted object.
2. Lease ownership is enforced by task state and lease expiry.
3. Retry decisions are centralized and policy-based.
4. Unknown failures do not become silent success.
5. Recovery records can store structured actions and outcomes.

Production use note:
- These are the foundational reliability primitives for the broader ADAI engineering architecture.
- Real provider integrations and worker supervision should extend these primitives rather than bypass them.
