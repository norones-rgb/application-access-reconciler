# Five minute demonstration

## 1. Explain the operational problem

An authoritative identity source and a SaaS export can disagree. This local tool identifies accounts that need a review and produces an explanation for every finding.

## 2. Inspect the sample records

Open `sample_data/identities.csv` and `sample_data/accounts.csv`.

- `EMP-003` is terminated but `jira-003` is enabled.
- `jira-004` is disabled but marked as licensed.
- `jira-002` last logged in on June 1, 2026 and exceeds the 90-day threshold on November 2, 2026.
- `jira-005` maps to `EMP-999`, which is absent from the identity export.
- `conf-005` has no last-login evidence.
- `conf-006` and `conf-006-admin` may be an intentional pair; the tool requests review rather than choosing one to remove.
- `conf-unlinked` has no identity ID.

Every identifier is synthetic. The Jira and Confluence labels illustrate exported datasets; they do not imply API integration.

## 3. Run the assessment

From the project root on Windows:

```powershell
py -m access_reconciler --identities sample_data/identities.csv --accounts sample_data/accounts.csv --as-of 2026-11-02 --output reports/demo
```

Use `python3` instead of `py` on macOS or Linux. If you already ran the command, select another output directory, such as `reports/demo-2`.

## 4. Open the report

Open `reports/demo/report.html`. Explain the difference between 7 findings and 8 accounts with findings: the duplicate-account finding covers two accounts. Show the CSV review queue and JSON assessment metadata.

Change `--stale-days` to 180 and choose a new output folder. The June 1 Jira account is no longer stale under that threshold, so the finding count falls from 7 to 6. This is a policy sensitivity demonstration, not evidence that the account became safe.

## 5. Show verification and limits

Run `py -m unittest discover -s tests -v`. Explain the tests for missing data, duplicate IDs, and report escaping. State that the tool performs no access or license changes and that exports must be validated by an authorized reviewer.
