# Interview discussion notes

Use these notes to understand and discuss the project, not as claims of production deployment.

## How to describe it

“This independent project reconciles employee identity records against application account exports. It creates a review queue for access and license hygiene. I used synthetic data so I could demonstrate the controls without exposing company information. The implementation is AI-assisted; I can explain the matching rules, validation, reports, and tests.”

Only say the last part once you have worked through the code and can answer follow-up questions yourself.

## Questions to practice

| Question | Design rationale to explain |
| --- | --- |
| Why not automatically disable unmatched accounts? | An unmatched record can reflect incomplete exports or failed identity correlation. Owner validation comes first. |
| Why not match on names? | Names are not unique or stable identity keys. The input contract uses an explicit authoritative ID. |
| Why is an empty login field informational? | It might mean missing telemetry rather than inactivity. The tool does not invent an activity date. |
| Why group duplicate accounts? | Separate administrative accounts can be intentional. The tool identifies the group without arbitrarily selecting an account to remove. |
| Why not estimate savings? | The exports do not include contract terms, pricing tiers, or whether reclamation actually changes the bill. |
| How would you extend it? | Add owner attestations, approved exceptions with expiry, input provenance, and contract-aware license analysis before live integrations. |
| What does the test suite establish? | Rule behavior, validation, deterministic output, report escaping, and input preservation for covered cases. It does not prove enterprise readiness. |

## Read the implementation

1. Follow `main()` in `access_reconciler/cli.py` from arguments to CSV loading, reconciliation, and reporting.
2. Inspect `validate()` in `engine.py`. Try an unknown identity status and observe the error.
3. Inspect the enabled-account branch in `reconcile()` and explain each finding.
4. Review `groups` and explain why the duplicate-account rule has several affected IDs.
5. Change the threshold and add a synthetic test record. Predict the result before running it.

## Résumé wording after familiarization

**Application Access Reconciler | Python, CSV, operational reporting**

Developed an AI-assisted, read-only reconciliation tool comparing employee identities with application account exports; generated HTML, CSV, and JSON review reports for lifecycle access gaps, stale accounts, and license hygiene, with automated validation and rule tests.

Add a verified repository URL after publication. Do not claim a production rollout, live SaaS connectors, real savings, or a user population from the sample dataset.
