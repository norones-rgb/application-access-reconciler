import csv
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from access_reconciler.cli import main, render_html, spreadsheet_safe, write_reports
from access_reconciler.engine import InputError, load_csv, reconcile

TODAY = date(2026, 11, 2)


class ReconcilerTests(unittest.TestCase):
    def account(self, **changes):
        result = dict(app="Jira", account_id="a1", identity_id="u1", enabled="true", licensed="true", last_login="2026-11-01")
        result.update(changes)
        return result

    def run_rules(self, accounts, status="active", **options):
        return reconcile([dict(identity_id="u1", status=status)], accounts, as_of=TODAY, **options)

    def test_clean_account(self):
        self.assertEqual(self.run_rules([self.account()])["finding_count"], 0)

    def test_terminated_and_inactive_access(self):
        for status in ("terminated", "inactive"):
            with self.subTest(status=status):
                report = self.run_rules([self.account()], status)
                self.assertEqual(report["findings"][0]["rule"], "INACTIVE_IDENTITY_ACCESS")
                self.assertEqual(report["severity_counts"]["high"], 1)

    def test_unmatched_and_unlinked_are_review_candidates(self):
        for key in ("missing", ""):
            report = self.run_rules([self.account(identity_id=key)])
            self.assertEqual(report["findings"][0]["rule"], "UNMATCHED_IDENTITY")
            self.assertTrue(report["findings"][0]["review_required"])

    def test_inactivity_boundary(self):
        for days, count in ((89, 0), (90, 0), (91, 1)):
            report = self.run_rules([self.account(last_login=(TODAY - timedelta(days=days)).isoformat())])
            self.assertEqual(report["finding_count"], count)

    def test_missing_login_is_not_stale(self):
        report = self.run_rules([self.account(last_login="")])
        self.assertEqual([f["rule"] for f in report["findings"]], ["MISSING_LOGIN_DATA"])
        self.assertEqual(report["severity_counts"]["info"], 1)

    def test_disabled_licensed_and_unlicensed(self):
        self.assertEqual(self.run_rules([self.account(enabled="false")])["findings"][0]["rule"], "DISABLED_LICENSED_ACCOUNT")
        self.assertEqual(self.run_rules([self.account(enabled="false", licensed="false")])["finding_count"], 0)

    def test_multiple_accounts_grouped_without_selecting_a_victim(self):
        report = self.run_rules([self.account(), self.account(account_id="admin")])
        self.assertEqual(report["finding_count"], 1)
        self.assertEqual(report["accounts_with_findings"], 2)
        self.assertEqual(report["findings"][0]["account_ids"], ["a1", "admin"])

    def test_same_account_id_in_different_apps_is_valid(self):
        report = self.run_rules([self.account(), self.account(app="Confluence")])
        self.assertEqual(report["finding_count"], 0)

    def test_reject_ambiguous_exports(self):
        with self.assertRaises(InputError):
            self.run_rules([self.account(), self.account()])
        with self.assertRaises(InputError):
            reconcile([], [self.account()], as_of=TODAY)
        with self.assertRaises(InputError):
            reconcile([dict(identity_id="u1", status="active")] * 2, [], as_of=TODAY)

    def test_reject_bad_values(self):
        for change in (dict(enabled="yes"), dict(licensed="1"), dict(last_login="invalid"), dict(last_login="2027-01-01")):
            with self.subTest(change=change), self.assertRaises(InputError):
                self.run_rules([self.account(**change)])
        with self.assertRaises(InputError):
            self.run_rules([self.account()], "unexpected")
        with self.assertRaises(InputError):
            self.run_rules([self.account()], stale_days=0)

    def test_reproducible_despite_input_order(self):
        accounts = [self.account(account_id="b", identity_id="unknown"), self.account(account_id="a", last_login="")]
        self.assertEqual(self.run_rules(accounts), self.run_rules(list(reversed(accounts))))

    def test_output_escaping_and_formula_neutralization(self):
        report = self.run_rules([self.account(app='<script>alert("x")</script>', account_id='=1+1', identity_id="missing")])
        rendered = render_html(report)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        for value in ('=1+1', '+cmd', '-2', '@SUM(A1)', '  =1'):
            self.assertTrue(spreadsheet_safe(value).startswith("'"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report"
            write_reports(report, output)
            with (output / "findings.csv").open(newline="") as handle:
                row = next(csv.DictReader(handle))
                self.assertEqual(row["account_ids"], "'=1+1")
            with self.assertRaises(InputError):
                write_reports(report, output)

    def test_csv_schema_and_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            for content in ("wrong\nx\n", "identity_id,identity_id\nu1,u1\n", "identity_id,status\nu1,active,extra\n", "identity_id,status\nu1\n"):
                path.write_text(content)
                with self.assertRaises(InputError):
                    load_csv(path, {"identity_id", "status"})

    def test_demo_end_to_end_and_inputs_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        identity = root / "sample_data/identities.csv"
        accounts = root / "sample_data/accounts.csv"
        before = (identity.read_bytes(), accounts.read_bytes())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result"
            code = main(["--identities", str(identity), "--accounts", str(accounts), "--as-of", str(TODAY), "--output", str(output)])
            self.assertEqual(code, 0)
            report = json.loads((output / "findings.json").read_text())
            self.assertEqual(report["finding_count"], 7)
            self.assertEqual(report["accounts_with_findings"], 8)
            self.assertEqual(report["severity_counts"], {"high": 1, "medium": 5, "info": 1})
            self.assertEqual(len(list(output.iterdir())), 3)
        self.assertEqual(before, (identity.read_bytes(), accounts.read_bytes()))


if __name__ == "__main__":
    unittest.main()
