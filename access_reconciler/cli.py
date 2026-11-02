import argparse
import csv
import html
import json
import os
from datetime import date
from pathlib import Path
import shutil
import tempfile

from .engine import InputError, load_csv, reconcile

IDENTITY_COLUMNS = {"identity_id", "status"}
ACCOUNT_COLUMNS = {"app", "account_id", "identity_id", "enabled", "licensed", "last_login"}


def spreadsheet_safe(value):
    """Neutralize spreadsheet formula prefixes, including whitespace-prefixed ones."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def render_html(report):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = "".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in (
            f["finding_id"], f["severity"], f["rule"], f["app"],
            ", ".join(f["account_ids"]), f["identity_id"], f["evidence"], f["recommendation"]
        )) + "</tr>" for f in report["findings"]
    ) or '<tr><td colspan="8">No findings for these rules in the supplied exports.</td></tr>'
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Application Access Review</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;background:#f5f6f8;color:#172235;margin:0;padding:36px}}main{{max-width:1500px;margin:auto}}h1{{margin-bottom:6px}}.muted{{color:#506078}}.metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:28px 0}}.metric{{background:white;padding:18px 24px;border:1px solid #d5dce5;border-radius:8px}}.metric strong{{display:block;font-size:30px}}.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}th,td{{text-align:left;border:1px solid #d5dce5;padding:12px;vertical-align:top}}th{{background:#e9eef5}}td{{overflow-wrap:anywhere}}footer{{margin-top:24px}}@media print{{body{{padding:0;background:white}}.scroll{{overflow:visible}}}}</style>
<main><p class="muted">ACCESS RECONCILER · READ ONLY</p><h1>Application Access Review</h1>
<p class="muted">Assessment: {esc(report['assessment_date'])} · Inactivity threshold: more than {report['stale_days']} days</p>
<p>Review candidates from supplied employee and application exports. Findings require owner validation before action.</p>
<div class="metrics"><div class="metric">Identities<strong>{report['identity_count']}</strong></div><div class="metric">Accounts<strong>{report['account_count']}</strong></div><div class="metric">Findings<strong>{report['finding_count']}</strong></div><div class="metric">High priority<strong>{report['severity_counts']['high']}</strong></div><div class="metric">Accounts with findings<strong>{report['accounts_with_findings']}</strong></div></div>
<div class="scroll"><table><caption>Review findings and recommended next steps</caption><thead><tr>{''.join('<th scope="col">'+h+'</th>' for h in ['ID','Severity','Rule','Application','Accounts','Identity','Evidence','Review action'])}</tr></thead><tbody>{rows}</tbody></table></div>
<footer class="muted">No account changes are performed. Severity is rule based triage, not a validated risk score. Export completeness, account exceptions, licensing terms, and login coverage must be checked. One account may have multiple findings. No dollar savings are calculated.</footer></main></html>'''


def write_reports(report, output):
    output = Path(output)
    if output.exists():
        raise InputError("Output path already exists; choose a new folder to preserve prior evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".reconcile-", dir=output.parent))
    try:
        (stage / "findings.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        fields = ["finding_id", "rule", "severity", "app", "account_ids", "identity_id", "evidence", "recommendation", "review_required"]
        with (stage / "findings.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for finding in report["findings"]:
                row = dict(finding)
                row["account_ids"] = "; ".join(row["account_ids"])
                writer.writerow({key: spreadsheet_safe(value) for key, value in row.items()})
        (stage / "report.html").write_text(render_html(report), encoding="utf-8")
        # Recheck before publishing; the CLI is intended for a single local operator.
        if output.exists():
            raise InputError("Output path was created during processing; choose a new folder")
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconcile employee identities and app accounts without changing access.")
    parser.add_argument("--identities", type=Path, required=True)
    parser.add_argument("--accounts", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="Assessment date YYYY-MM-DD; specify for reproducible results")
    parser.add_argument("--stale-days", type=int, default=90)
    parser.add_argument("--output", type=Path, required=True, help="New report directory; existing paths are not overwritten")
    args = parser.parse_args(argv)
    try:
        report = reconcile(load_csv(args.identities, IDENTITY_COLUMNS),
                           load_csv(args.accounts, ACCOUNT_COLUMNS),
                           as_of=args.as_of, stale_days=args.stale_days)
        write_reports(report, args.output)
    except (InputError, OSError, UnicodeError, csv.Error) as exc:
        parser.exit(2, f"Input/report error: {exc}\n")
    print(f"Reviewed {report['account_count']} accounts; {report['finding_count']} findings across {report['accounts_with_findings']} accounts.")
    print(f"Reports: {args.output}")
    return 0
