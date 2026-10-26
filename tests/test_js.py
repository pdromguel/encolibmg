"""Runs the front-end unit tests (Node's built-in runner) when Node is installed."""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = sorted((Path(__file__).parent / "js").glob("*.test.mjs"))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
@pytest.mark.parametrize("path", JS_TESTS, ids=lambda p: p.name)
def test_js(path):
    proc = subprocess.run(["node", "--test", str(path)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
