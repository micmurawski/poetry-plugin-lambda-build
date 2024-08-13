from __future__ import annotations  # noqa: D100

import os
import subprocess
import sys
import zipfile
from typing import TYPE_CHECKING

from poetry_plugin_lambda_build.utils import remove_prefix, run_cmd

if TYPE_CHECKING:
    from logging import Logger


def run_python_cmd(  # noqa: D103
    *cmd: str,
    logger: Logger | None = None,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs,  # noqa: ANN003
) -> int:
    return run_cmd(
        sys.executable, *cmd, logger=logger, stdout=stdout, stderr=stderr, **kwargs
    )


def run_poetry_cmd(*cmd: list[str]) -> int:  # noqa: D103
    return run_python_cmd("-m", "poetry", *cmd)


def update_pyproject_toml(**kwargs):  # noqa: ANN003, ANN201, D103
    with open("pyproject.toml", "a") as f:  # noqa: PTH123
        f.write("[tool.poetry-plugin-lambda-build]\n")
        for k, v in kwargs.items():
            f.write(f'{k} = "{v}" \n')


def assert_file_exists_in_dir(  # noqa: D103
    dirname: str, base_path: str | None = None, files: list | None = None
) -> None:
    _files = []
    for _base, __, __files in os.walk(dirname):
        _base = remove_prefix(_base, dirname + "/")
        _files += [os.path.join(_base, f) for f in __files]  # noqa: PTH118
    _files = set(_files)

    if files is None:
        files = []
    if base_path:
        for file_path in _files:
            assert file_path.startswith(
                base_path
            ), f"Install directory is wrong for {file_path} {base_path}."

    for file in files:
        assert file in _files, f"{file} does not exists in {dirname}"


def assert_file_not_exists_in_dir(dirname: str, files: list | None = None):  # noqa: ANN201, D103
    _files = []
    for _base, __, __files in os.walk(dirname):
        _base = remove_prefix(_base, dirname + "/")
        _files += [os.path.join(_base, f) for f in __files]  # noqa: PTH118
    _files = set(_files)

    if files is None:
        files = []

    for file in files:
        assert file not in _files, f"{file} exists in {dirname}"


def assert_file_exists_in_zip(  # noqa: D103
    filename: str, base_path: str | None = None, files: list | None = None
) -> None:
    zip_ = zipfile.ZipFile(filename)
    _list = zip_.namelist()
    if files is None:
        files = []
    if base_path:
        for file_path in _list:
            assert file_path.startswith(
                base_path
            ), f"Install directory is wrong for {file_path}."
    for file in files:
        assert file in _list, f"{file} does not exists in zip package"


def assert_file_not_exists_in_zip(filename: str, files: list | None = None):  # noqa: ANN201, D103
    zip_ = zipfile.ZipFile(filename)
    _list = zip_.namelist()
    if files is None:
        files = []
    for file in files:
        assert file not in _list, f"{file} exists in zip package"
