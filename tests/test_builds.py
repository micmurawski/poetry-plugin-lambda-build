import contextlib
import os
import platform
import subprocess
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def vars():
    if platform.system() == "Darwin":
        return 'export DOCKER_HOST="unix:///Users/$USER/.docker/run/docker.sock" &&'
    return ""


@contextlib.contextmanager
def cd(path):
    old_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)


def _run_process(cmd: str):
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = process.communicate()
    if process.returncode == 0:
        assert True
    elif process.returncode == 1:
        assert False, f"{cmd} resulted with {err.decode('utf-8')}"
    return out.decode("utf-8")


def _update_pyproject_toml(**kwargs):
    with open("pyproject.toml", "a") as f:
        f.write("[tool.poetry-plugin-lambda-build]\n")
        for k, v in kwargs.items():
            f.write(f'{k} = "{v}" \n')


def assert_exists_zip_file(filename: str, base_path: str = None, files: list = None):
    zip = zipfile.ZipFile(filename)
    _list = zip.namelist()
    if files is None:
        files = []
    if base_path:
        for file_path in _list:
            assert file_path.startswith(
                base_path), f"Install directory is wrong for {file_path}."
    for file in files:
        assert file in _list, f"{file} does not exists in zip package"


def assert_not_exists_zip_file(filename: str, base_path: str = None, files: list = None):
    zip = zipfile.ZipFile(filename)
    _list = zip.namelist()
    if files is None:
        files = []
    for file in files:
        assert file not in _list, f"{file} exists in zip package"


PARAMS = [
    (
        {
            "docker_image": "public.ecr.aws/sam/build-python3.11:latest-x86_64",
            "layer_install_dir": "python",
            "layer_artifact_path": "layer.zip",
            "function_artifact_path": "function.zip"
        },
        {},
        [
            lambda: assert_exists_zip_file("layer.zip", "python"),
            lambda: assert_not_exists_zip_file(
                "layer.zip",
                files=["python/requirements.txt"]
            ),
            lambda: assert_exists_zip_file(
                "function.zip",
                files=["test_project/handler.py"]
            )
        ]
    ),
    (
        {
            "layer_install_dir": "python",
            "layer_artifact_path": "layer.zip",
            "function_artifact_path": "function.zip"
        },
        {},
        [
            lambda: assert_exists_zip_file("layer.zip", "python"),
            lambda: assert_not_exists_zip_file(
                "layer.zip",
                files=["python/requirements.txt"]
            ),
            lambda: assert_exists_zip_file(
                "function.zip",
                files=["test_project/handler.py"]
            )
        ]
    ),
    (
        {
            "artifact_path": "function.zip",
            "install_dir": "python"
        },
        {},
        [
            lambda: assert_exists_zip_file(
                "function.zip",
                files=["python/test_project/handler.py"]
            ),
            lambda: assert_not_exists_zip_file(
                "function.zip",
                files=["python/requirements.txt"]
            ),
        ]
    ),
    (
        {
            "artifact_path": "function.zip",
            "without": "test"
        },
        {},
        [
            lambda: assert_exists_zip_file(
                "function.zip",
                files=["test_project/handler.py"]
            ),
            lambda: assert_not_exists_zip_file(
                "function.zip",
                files=["pytest/__init__.py"]
            )
        ]
    )
]


@pytest.mark.parametrize("config,args,assert_files", PARAMS)
def test_build_in_container(config: dict, args: dict, assert_files: list, vars, tmp_path: Path, ):
    with cd(tmp_path):
        handler_file = "test_project/handler.py"
        _run_process("poetry new test-project")
        with cd(tmp_path / "test-project"):
            _run_process("poetry add requests")
            _run_process("poetry add pytest --group=test")
            _run_process("poetry self add poetry-plugin-export")
            open(handler_file, "w").close()
            if config:
                _update_pyproject_toml(
                    **config
                )
            arguments = " ".join(f'{k}="{v}"' for k, v in args.items())
            _run_process(f"{vars} poetry build-lambda {arguments} -vvv")
            for files_assertion in assert_files:
                files_assertion()
