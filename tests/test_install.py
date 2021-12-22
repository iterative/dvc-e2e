import json
import os
import subprocess
from itertools import chain, repeat
from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING, Iterable, List, Tuple, TypeVar, Union

import pytest
from pytest_virtualenv import VirtualEnv  # type: ignore

from . import DEFAULT

if TYPE_CHECKING:
    from . import TestConfig

T = TypeVar("T")


def ensure_list(arg: Union[str, Iterable[str]]) -> List[str]:
    return [arg] if isinstance(arg, str) else list(arg)


def build_spec(
    pkg: str,
    url: str = None,
    rev: str = None,
    version: str = None,
    extras: Union[str, List[str]] = None,
) -> str:
    spec = url or pkg
    if url and rev:
        spec += f"@{rev}"
    if url:
        spec += f"#egg={pkg}"
    if extras:
        spec += f"[{','.join(ensure_list(extras))}]"
    if version and not url:
        spec += f"=={version}"
    return spec


class Installer:
    def setup(self: "T") -> "T":
        return self

    def install(
        self,
        pkg: str,
        url: str = None,
        rev: str = None,
        version: str = None,
        extras: Union[str, List[str]] = None,
        verbose: bool = False,
    ) -> None:
        pass

    def is_installed(self, pkg: str) -> bool:
        pass


class PythonInstaller(Installer):
    def __init__(self, virtualenv: "VirtualEnv") -> None:
        self.virtualenv: "VirtualEnv" = virtualenv
        super().__init__()

    def run(self, args, **kwargs):
        cmd, *rest = args
        if os.name == "nt":
            # In virtualenv on windows "Scripts" folder is used instead of "bin".
            executable = str(self.virtualenv.virtualenv / "Scripts" / cmd + ".exe")
        else:
            executable = str(self.virtualenv.virtualenv / "bin" / cmd)
        return self.virtualenv.run(
            [self.virtualenv.python, executable, *rest], **kwargs
        )


class PipInstaller(PythonInstaller):
    def install(
        self,
        pkg: str,
        url: str = None,
        rev: str = None,
        version: str = None,
        extras: Union[str, List[str]] = None,
        verbose: bool = False,
    ) -> None:
        args: "Tuple[str, ...]" = "pip", "install"
        if verbose:
            args = *args, "--verbose"
        if not version:
            args = *args, "--upgrade"
        spec = build_spec(pkg, url=url, rev=rev, version=version, extras=extras)
        print(f"\nInstalling {pkg} with pip\n")
        self.run([*args, spec])

    def is_installed(self, pkg: str) -> bool:
        return pkg in self.virtualenv.installed_packages()


class PoetryInstaller(PythonInstaller):
    def __init__(self, virtualenv: VirtualEnv, pip: PipInstaller) -> None:
        super().__init__(virtualenv)
        self.pip: "PipInstaller" = pip

    def setup(self) -> "PoetryInstaller":
        self.pip.install("poetry")
        assert self.pip.is_installed("poetry")
        self.run(["poetry", "init", "-n"], capture=True)
        return self

    def install(
        self,
        pkg: str,
        url: str = None,
        rev: str = None,
        version: str = None,
        extras: Union[str, List[str]] = None,
        verbose: bool = False,
    ) -> None:
        args: "Tuple[str, ...]" = "poetry", "add"
        if verbose:
            args = *args, "-vvv"

        spec = url or pkg
        if not url:
            spec += "@latest" if not version else f"=={version}"
        elif rev:
            # poetry defaults to `master` by default, so always specify `rev` for git urls.
            # see: https://github.com/python-poetry/poetry/issues/3366.
            spec += f"#{rev}"
        print(f"\nInstalling {pkg} with Poetry\n")

        self.run(
            [
                *args,
                spec,
                *chain.from_iterable(
                    zip(repeat("--extras"), ensure_list(extras or []))
                ),
            ]
        )

    def is_installed(self, pkg: str) -> bool:
        try:
            self.run(["poetry", "show", pkg])
            return True
        except subprocess.CalledProcessError as exc:
            print(exc.stdout)
            if exc.returncode == 1:
                return False
            raise


class PipxInstaller(PythonInstaller):
    def __init__(self, virtualenv: VirtualEnv, pip: PipInstaller) -> None:
        super().__init__(virtualenv)
        self.pip: "PipInstaller" = pip

    def setup(self) -> "PipxInstaller":
        self.pip.install("pipx")
        assert self.pip.is_installed("pipx")
        return self

    def install(
        self,
        pkg: str,
        url: str = None,
        rev: str = None,
        version: str = None,
        extras: Union[str, List[str]] = None,
        verbose: bool = False,
    ) -> None:
        args: "Tuple[str, ...]" = "pipx", "install"
        if verbose:
            args = *args, "--verbose"
        if not version:
            args = *args, "--pip-args=--upgrade"

        spec = build_spec(pkg, url=url, rev=rev, version=version, extras=extras)
        print(f"\nInstalling {pkg} with pipx\n")
        self.run([*args, spec])

    def is_installed(self, pkg: str) -> bool:
        out = self.run(["pipx", "list", "--json"], capture=True)
        print(out)
        data = json.loads(out)
        return pkg in data["venvs"]


class PipenvInstaller(PythonInstaller):
    def __init__(self, virtualenv: VirtualEnv, pip: PipInstaller) -> None:
        super().__init__(virtualenv)
        self.pip: "PipInstaller" = pip

    def setup(self) -> "PipenvInstaller":
        self.pip.install("pipenv")
        assert self.pip.is_installed("pipenv")
        return self

    def install(
        self,
        pkg: str,
        url: str = None,
        rev: str = None,
        version: str = None,
        extras: Union[str, List[str]] = None,
        verbose: bool = False,
    ) -> None:
        args: "Tuple[str, ...]" = "pipenv", "install"
        if verbose:
            args = *args, "--verbose"
        spec = build_spec(pkg, url=url, rev=rev, version=version, extras=extras)
        print(f"\nInstalling {pkg} with pipenv\n")
        self.run([*args, spec])

    def is_installed(self, pkg: str) -> bool:
        out = self.run(["pipenv", "graph", "--json"], capture=True)
        print(out)
        data = json.loads(out)
        installed_packages: List[str] = list(
            filter(None, (entry.get("package", {}).get("key") for entry in data))
        )
        return pkg in installed_packages


@pytest.fixture
def pip(virtualenv: VirtualEnv) -> PipInstaller:
    virtualenv.debug = True
    return PipInstaller(virtualenv).setup()


@pytest.fixture
def poetry(virtualenv: "VirtualEnv", pip: PipInstaller) -> PoetryInstaller:
    return PoetryInstaller(virtualenv, pip).setup()


@pytest.fixture
def pipenv(virtualenv: "VirtualEnv", pip: PipInstaller) -> PipenvInstaller:
    return PipenvInstaller(virtualenv, pip).setup()


@pytest.fixture
def pipx(
    tmp_path: Path,
    virtualenv: "VirtualEnv",
    pip: PipInstaller,
) -> PipxInstaller:
    home_dir = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    virtualenv.env.update({"PIPX_HOME": str(home_dir), "PIPX_BIN_DIR": str(bin_dir)})
    return PipxInstaller(virtualenv, pip).setup()


@pytest.fixture
def installer(test_config: "TestConfig", request: pytest.FixtureRequest) -> "Installer":
    installer = request.param  # type: ignore
    if test_config.installer and test_config.installer != installer:
        pytest.skip(f"skipping installer '{installer}'")
    return request.getfixturevalue(installer)


@pytest.fixture
def extras(test_config: "TestConfig", request: pytest.FixtureRequest) -> str:
    extras = request.param  # type: ignore
    if test_config.extras is not DEFAULT and test_config.extras != extras:
        pytest.skip(f"skipping extras '{extras}'")
    return extras


@pytest.mark.parametrize(
    "extras",
    [
        # in order of being least trouble to very problematic installations
        None,
        "webdav",
        "oss",
        "ssh",
        "webhdfs",
        "gdrive",
        "azure",
        "gs",
        "hdfs",
        "s3",
        "all",
    ],
    indirect=True,
    ids=lambda e: str(e).lower(),
)
@pytest.mark.parametrize(
    "installer",
    [
        "pip",
        "pipx",
        "poetry",
        "pipenv",
    ],
    indirect=True,
)
def test_install(
    test_config: "TestConfig",
    extras: Union[str, List[str]],
    installer: Installer,
) -> None:
    pkg = "dvc"
    try:
        print(f"\nInstalling {pkg} with {installer.__class__.__name__}")
        installer.install(
            pkg,
            url=test_config.url,
            version=test_config.version,
            extras=extras,
            verbose=test_config.verbose,
            rev=test_config.rev,
        )
        assert installer.is_installed(pkg)
    except CalledProcessError as exc:
        print(exc.stdout)
        raise
