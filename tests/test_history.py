import history


def test_diff_returns_none_without_previous_snapshot():
    assert history.diff_snapshots(None, [], [], []) is None


def test_diff_reports_only_new_items():
    previous = {
        "timestamp": "20260101_000000",
        "processes": [{"name": "python.exe"}],
        "connections": [{"remote_addr": "1.1.1.1:443"}],
        "startup_items": [{"name": "onedrive"}],
    }
    diff = history.diff_snapshots(
        previous,
        [{"name": "python.exe"}, {"name": "unknown.exe"}],
        [{"remote_addr": "1.1.1.1:443"}, {"remote_addr": "8.8.8.8:53"}],
        [{"name": "onedrive"}, {"name": "new-service"}],
    )
    assert diff["previous_timestamp"] == "20260101_000000"
    assert diff["new_processes"] == ["unknown.exe"]
    assert diff["new_remote_connections"] == ["8.8.8.8:53"]
    assert diff["new_startup_items"] == ["new-service"]


def test_diff_ignores_error_entries():
    previous = {"processes": [], "connections": [], "startup_items": []}
    diff = history.diff_snapshots(previous, [{"error": "boom"}], [], [])
    assert diff["new_processes"] == []
