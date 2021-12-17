from pathlib import Path

import pytest
from _pytest.config import Config

from . import DEFAULT, TestConfig


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--url",
        default=None,
        help="URL of the package to install from",
    )
    parser.addoption(
        "--installer",
        default=None,
        help="Installer to use",
    )
    parser.addoption(
        "--extras",
        default=DEFAULT,
        help="Extras to install with",
    )
    parser.addoption("--pkg-version", default=None, help="Version to install")
    parser.addoption(
        "--rev",
        default=None,
        help="Revision to use",
    )


@pytest.fixture(scope="session")
def test_config(pytestconfig: Config):
    extras = pytestconfig.getoption("extras")
    if extras is not DEFAULT and extras.lower() == "none":
        extras = None

    return TestConfig(
        url=pytestconfig.getoption("--url"),
        installer=pytestconfig.getoption("installer"),
        extras=extras,
        version=pytestconfig.getoption("pkg_version"),
        verbose=pytestconfig.getoption("verbose") > 0,
        rev=pytestconfig.getoption("rev"),
    )


@pytest.fixture(autouse=True)
def change_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPENV_VERBOSITY", "-1")
