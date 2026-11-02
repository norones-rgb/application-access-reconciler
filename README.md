# Application Access Reconciler

A read-only Python tool that compares employee identity records with application account exports and produces an evidence-backed access review queue.

Built as an independent portfolio project by Ibrahima Aw, with AI-assisted implementation. The included Jira and Confluence exports are entirely synthetic. This project demonstrates reconciliation logic, identity controls, license hygiene, operational reporting, and documentation; it is not a record of an employer deployment.

## The problem

An application account can outlive the business reason for its access. Separate identity and application exports make those gaps hard to see: a terminated employee may retain an enabled account, a disabled account may still hold a license, or an enabled account may have no authoritative identity match.

This tool turns two CSV files into a review queue with the affected accounts, the rule that flagged them, the supporting evidence, and a recommended validation step. It does not disable accounts or change licenses.

## Quick start

Requires Python 3.10 or newer. The source checkout runs with the Python standard library; no package installation, API keys, or cloud account is required.

From the project folder on Windows:

```powershell
py -m access_reconciler --identities sample_data/identities.csv --accounts sample_data/accounts.csv --as-of 2026-11-02 --stale-days 90 --output reports/demo
py -m unittest discover -s tests -v
```

On macOS or Linux, use `python3` in place of `py`.

Open `reports/demo/report.html` in a browser. You can also open the included `demo_output/report.html` immediately without running Python.

Expected result:

```text
Reviewed 12 accounts; 7 findings across 8 accounts.
```

The demo contains 1 high-priority finding, 5 medium-priority findings, and 1 informational finding. One finding can cover multiple accounts, and one account can have multiple findings. These counts are not interchangeable.

Use a new output folder for each run. Existing report folders are never overwritten. Set `--as-of` explicitly when retaining assessment evidence so that the analysis is reproducible.

## What gets checked

| Rule | Condition | Priority | Required interpretation |
| --- | --- | --- | --- |
| `INACTIVE_IDENTITY_ACCESS` | Enabled account maps to an inactive or terminated employee | High | Confirm authoritative status and approved exceptions before remediation |
| `UNMATCHED_IDENTITY` | Enabled account has a blank or unmatched employee ID | Medium | Check identity mapping and export completeness; this does not prove an orphan account |
| `STALE_ENABLED_ACCOUNT` | Last login is more than the configured number of days before assessment | Medium | Check business need and authentication coverage before removing access |
| `DISABLED_LICENSED_ACCOUNT` | Disabled account remains marked as licensed | Medium | Review billing terms and retention before reclaiming a license |
| `MULTIPLE_ENABLED_ACCOUNTS` | Multiple enabled accounts in one app map to one identity | Medium | Separate admin and standard accounts can be intentional |
| `MISSING_LOGIN_DATA` | Enabled account has no last-login value | Informational | Missing evidence does not establish inactivity |

## Input contract

### Identities

```csv
identity_id,status
EMP-001,active
EMP-002,terminated
```

`identity_id` is required and unique. Status values are `active`, `inactive`, or `terminated`, ignoring case. The identity export must contain at least one identity.

### Application accounts

```csv
app,account_id,identity_id,enabled,licensed,last_login
Jira,jira-001,EMP-001,true,true,2026-10-30
```

- All six columns are required. Extra columns are accepted but not analyzed or included in reports.
- `app` and `account_id` must be nonempty. Account IDs are unique within an application, not globally.
- Matching uses exact, case-sensitive IDs after trimming surrounding whitespace. There is no email-based or fuzzy matching.
- A blank `identity_id` is permitted and becomes a review candidate if the account is enabled.
- `enabled` and `licensed` accept only `true` or `false`, ignoring case.
- `last_login` is a date in `YYYY-MM-DD` format or empty. Future dates relative to the assessment date are rejected.
- Each row must represent an employee-linked application account. Service accounts, bots, and shared accounts need a different ownership model and should be excluded before a real assessment.

## Output

| File | Purpose |
| --- | --- |
| `report.html` | Standalone review dashboard with summary counts, findings, and recommended actions |
| `findings.csv` | Spreadsheet-friendly review register; formula prefixes are neutralized |
| `findings.json` | Structured assessment metadata and findings for further analysis |

Findings are ordered deterministically by application and account ID, followed by duplicate-account groups. Each includes an ID, rule, priority, application, affected accounts, identity, evidence, recommendation, and `review_required: true`.

## Design decisions

- **CSV first:** supports a local demonstration and exported data without requiring tenant access. There are no live Jira, Confluence, Okta, or ServiceNow connectors.
- **Explicit identity keys:** avoids silently merging people by display name or guessing from email addresses.
- **Review before remediation:** automation produces evidence for a decision; account changes stay with authorized owners.
- **Deterministic date and ordering:** fixed inputs, assessment date, and threshold produce the same report content.
- **Validate before reporting:** malformed rows, duplicate keys, unknown statuses, and invalid dates stop the run instead of producing misleading findings.
- **Local reports:** the HTML loads no external resources and contains no JavaScript. Exported strings are HTML-escaped; CSV formula prefixes are neutralized.

The code separates input validation and rules (`engine.py`) from CLI parsing and report generation (`cli.py`).

## Verification

The test suite includes an end-to-end demo, identity and account key validation, inactivity boundaries, missing login data, disabled-license detection, grouped duplicate accounts, reproducibility, HTML escaping, CSV formula neutralization, output preservation, and unchanged input bytes.

```powershell
py -m unittest discover -s tests -v
```

## Limits

This is a portfolio prototype, not a certified control or production IAM platform. It trusts the supplied exports, keeps data in memory, and does not calculate license savings, validate employment events, evaluate entitlements, or prove that access is exploitable. Priority reflects rule-based triage, not a validated risk score. A clean report only means these rules found no matches in these inputs.

The report publication flow is intended for a single local operator, not concurrent writers. There is no authentication, encryption at rest, multi-user workflow, or remediation connection. Reports contain supplied account identifiers and should be handled according to the data's sensitivity. Public examples must remain synthetic.

## Portfolio notes

See [the demo walkthrough](docs/DEMO.md), [interview discussion notes](docs/INTERVIEW.md), and [the roadmap](docs/ROADMAP.md). Understand and test the implementation before presenting it as a project you can maintain.

## License

MIT. See [LICENSE](LICENSE).
