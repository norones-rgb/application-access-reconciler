"""Deterministic rules over validated employee and application exports."""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


class InputError(ValueError):
    """An input cannot be reconciled safely."""


def load_csv(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise InputError(f"{Path(path).name}: duplicate column names")
        if not required.issubset(headers):
            raise InputError(f"{Path(path).name}: missing columns: {', '.join(sorted(required - set(headers)))}")
        rows = []
        for number, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise InputError(f"{Path(path).name}: malformed CSV row {number}")
            rows.append({key: value.strip() for key, value in raw.items()})
        return rows


def validate(identities, accounts, as_of):
    people = {}
    for row in identities:
        key = row["identity_id"]
        if not key or key in people:
            raise InputError("identity_id must be nonempty and unique")
        status = row["status"].lower()
        if status not in {"active", "inactive", "terminated"}:
            raise InputError(f"Unknown identity status for {key}")
        people[key] = {"identity_id": key, "status": status}
    if not people:
        raise InputError("Identity export is empty; refusing to classify every account as unmatched")
    seen = set()
    normalized = []
    for row in accounts:
        key = (row["app"], row["account_id"])
        if not all(key) or key in seen:
            raise InputError("app and account_id must be nonempty; account_id must be unique within each app")
        seen.add(key)
        account = dict(row)
        for field in ("enabled", "licensed"):
            value = row[field].lower()
            if value not in {"true", "false"}:
                raise InputError(f"{key}: {field} must be true or false")
            account[field] = value == "true"
        value = row["last_login"]
        try:
            login = date.fromisoformat(value) if value else None
        except ValueError as exc:
            raise InputError(f"{key}: last_login must be YYYY-MM-DD or empty") from exc
        if login and login > as_of:
            raise InputError(f"{key}: last_login is after the assessment date")
        account["last_login"] = login
        normalized.append(account)
    return people, sorted(normalized, key=lambda row: (row["app"], row["account_id"]))


def reconcile(identities, accounts, *, as_of, stale_days=90):
    if stale_days < 1:
        raise InputError("stale_days must be at least 1")
    people, accounts = validate(identities, accounts, as_of)
    findings = []

    def add(rule, severity, account, evidence, recommendation, account_ids=None):
        findings.append({
            "finding_id": f"F-{len(findings) + 1:04d}",
            "rule": rule, "severity": severity, "app": account["app"],
            "account_ids": account_ids or [account["account_id"]],
            "identity_id": account["identity_id"], "evidence": evidence,
            "recommendation": recommendation, "review_required": True,
        })

    groups = defaultdict(list)
    for account in accounts:
        identity = people.get(account["identity_id"])
        if account["enabled"]:
            if not identity:
                add("UNMATCHED_IDENTITY", "medium", account,
                    "Enabled account has no matching identity in the supplied authoritative export.",
                    "Verify export completeness and identity mapping with the application owner before changing access.")
            elif identity["status"] != "active":
                add("INACTIVE_IDENTITY_ACCESS", "high", account,
                    f"Enabled account maps to an identity marked {identity['status']}.",
                    "Confirm employment status and approved exceptions; prioritize access review with the owner.")
            login = account["last_login"]
            if login:
                age = (as_of - login).days
                if age > stale_days:
                    add("STALE_ENABLED_ACCOUNT", "medium", account,
                        f"Last login {login.isoformat()}; {age} days before assessment, exceeding {stale_days} days.",
                        "Confirm ongoing business need and authentication log coverage; review access and license allocation.")
            else:
                add("MISSING_LOGIN_DATA", "info", account,
                    "Enabled account has no last-login value; inactivity cannot be established.",
                    "Obtain authentication evidence; missing data alone is not a reason to remove access.")
            if identity:
                groups[(account["app"], account["identity_id"])].append(account)
        elif account["licensed"]:
            add("DISABLED_LICENSED_ACCOUNT", "medium", account,
                "Account is disabled but still marked as licensed in the supplied export.",
                "Review subscription terms, retention requirements, and reassignment options before reclaiming a license.")
    for key in sorted(groups):
        members = groups[key]
        if len(members) > 1:
            add("MULTIPLE_ENABLED_ACCOUNTS", "medium", members[0],
                f"{len(members)} enabled accounts in this app map to the same identity.",
                "Check whether separate admin and standard accounts are intentional; retain approved exceptions.",
                account_ids=[row["account_id"] for row in members])
    counts = {severity: sum(f["severity"] == severity for f in findings)
              for severity in ("high", "medium", "info")}
    return {"assessment_date": as_of.isoformat(), "stale_days": stale_days,
            "identity_count": len(people), "account_count": len(accounts),
            "finding_count": len(findings),
            "accounts_with_findings": len({(f["app"], key) for f in findings for key in f["account_ids"]}),
            "severity_counts": counts, "findings": findings}
