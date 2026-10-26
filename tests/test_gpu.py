import subprocess

from encolibmg.core import gpu


def fake_smi(monkeypatch, stdout=None, error=None):
    def run(*a, **k):
        if error:
            raise error
        return subprocess.CompletedProcess(a, 0, stdout=stdout, stderr="")
    monkeypatch.setattr(gpu.subprocess, "run", run)


def test_recent_card_is_used(monkeypatch):
    fake_smi(monkeypatch, "12.0\n")
    env = {}
    assert gpu.choose_device(env) == "gpu" and env == {}


def test_oldest_supported_card_is_used(monkeypatch):
    fake_smi(monkeypatch, "6.1\n")  # GTX 10 series
    assert gpu.choose_device({}) == "gpu"


def test_too_old_card_is_hidden(monkeypatch):
    fake_smi(monkeypatch, "5.2\n")  # GTX 900 series
    env = {}
    assert gpu.choose_device(env) == "cpu-old-gpu"
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"


def test_no_card_or_driver(monkeypatch):
    fake_smi(monkeypatch, error=FileNotFoundError("nvidia-smi"))
    env = {}
    assert gpu.choose_device(env) == "cpu" and env == {}


def test_two_cards_use_the_first_line(monkeypatch):
    fake_smi(monkeypatch, "8.6\n5.0\n")
    assert gpu.nvidia_capability() == (8, 6)


def test_user_setting_wins(monkeypatch):
    fake_smi(monkeypatch, "5.2\n")
    assert gpu.choose_device({"CUDA_VISIBLE_DEVICES": "0"}) == "gpu"
    assert gpu.choose_device({"CUDA_VISIBLE_DEVICES": "-1"}) == "cpu"
