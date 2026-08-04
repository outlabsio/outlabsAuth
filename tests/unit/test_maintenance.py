from __future__ import annotations

from outlabs_auth import MaintenanceReport


def test_maintenance_report_accepts_complete_error_free_results() -> None:
    report = MaintenanceReport.from_results(
        {
            "token_cleanup": {"refresh_tokens": {"total": 2}},
            "api_key_usage_sync": {"synced_keys": 3, "errors": 0},
        },
        expected_steps=("token_cleanup", "api_key_usage_sync"),
    )

    assert report.ok is True
    assert report.completed_steps == ("token_cleanup", "api_key_usage_sync")
    assert report.missing_steps == ()
    assert report.error_steps == ()
    assert report.reported_errors == 0


def test_maintenance_report_rejects_missing_steps_and_step_errors() -> None:
    report = MaintenanceReport.from_results(
        {
            "activity_sync": {"processed": 5, "errors": 2},
            "diagnostic": {"errors": True},
        },
        expected_steps=("token_cleanup", "activity_sync", "api_key_usage_sync"),
    )

    assert report.ok is False
    assert report.missing_steps == ("token_cleanup", "api_key_usage_sync")
    assert report.error_steps == ("activity_sync",)
    assert report.reported_errors == 2
