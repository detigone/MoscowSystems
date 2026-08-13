from __future__ import annotations

from datetime import datetime, timezone

from bot.services.ticket_automation import ConfigIssue, MaintenanceReport, _parse_db_time


def test_parse_db_time_iso_with_z():
    dt = _parse_db_time("2026-08-13T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2026


def test_parse_db_time_naive_gets_utc():
    dt = _parse_db_time("2026-08-13 12:00:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc


def test_parse_db_time_invalid():
    assert _parse_db_time("not-a-date") is None
    assert _parse_db_time(None) is None


def test_maintenance_report_defaults():
    report = MaintenanceReport()
    assert report.orphans_closed == 0
    assert report.idle_closed == 0
    assert report.reminders_sent == 0
    assert report.panel_repaired is False
    assert report.issues == []


def test_config_issue_levels():
    issue = ConfigIssue("warn", "Test")
    assert issue.level == "warn"
    assert issue.text == "Test"
