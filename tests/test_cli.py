# tests/test_cli.py

import psutil
import pytest

from procwatch import cli


def test_parse_args_name_only():
    args = cli.parse_args(["--name", "sshd"])
    assert args.name == "sshd"
    assert args.pid is None
    assert args.port is None


def test_port():
    port = 10
    res = cli.valid_port(port)
    assert res


def test_pid():
    pid = 10009
    res = cli.valid_pid(pid)
    assert res


# ----------------------------
# Test: valid PID returns process
# ----------------------------
def test_filter_by_pid_success(monkeypatch):
    class DummyProcess:
        def __init__(self, pid):
            self.pid = pid

    def mock_process(pid):
        return DummyProcess(pid)

    monkeypatch.setattr(psutil, "Process", mock_process)

    result = cli.filter_by_pid(123)
    assert result is not None
    assert result.pid == 123


# ----------------------------
# Test: psutil.Error → returns None
# ----------------------------
def test_filter_by_pid_psutil_error(monkeypatch):
    def mock_process(pid):
        raise psutil.Error()

    monkeypatch.setattr(psutil, "Process", mock_process)

    result = cli.filter_by_pid(123)
    assert result is None


# ----------------------------
# Test: ValueError → SystemExit
# ----------------------------
def test_filter_by_pid_value_error(monkeypatch):
    def mock_process(pid):
        raise ValueError()

    monkeypatch.setattr(psutil, "Process", mock_process)

    with pytest.raises(SystemExit) as exc:
        cli.filter_by_pid(123)

    assert exc.value.code == 1


# ----------------------------
# Test: TypeError → SystemExit
# ----------------------------
def test_filter_by_pid_type_error(monkeypatch):
    def mock_process(pid):
        raise TypeError()

    monkeypatch.setattr(psutil, "Process", mock_process)

    with pytest.raises(SystemExit) as exc:
        cli.filter_by_pid("invalid")

    assert exc.value.code == 1


def test_restart_service():
    command = "echo hi"
    is_restarted = cli.restart_service(command=command)
    assert is_restarted
