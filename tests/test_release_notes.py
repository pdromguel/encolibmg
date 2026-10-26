import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_notes import section  # noqa: E402

TEXT = """# Changelog

## [Unreleased]
- next thing

## [1.0.0] - 2026-10-27
### Added
- the installer

## [0.9.0] - 2026-10-25
- first release

[0.9.0]: https://example.com
"""


def test_section_of_a_version():
    assert section("1.0.0", TEXT) == "### Added\n- the installer\n"
    assert section("0.9.0", TEXT) == "- first release\n"
    with pytest.raises(SystemExit):
        section("2.0.0", TEXT)


def test_the_real_changelog_has_the_current_version():
    from encolibmg import __version__

    assert section(__version__).strip()
