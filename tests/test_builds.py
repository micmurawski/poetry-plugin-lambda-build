import contextlib
import os
import platform
import subprocess
import zipfile
from pathlib import Path

import pytest

from poetry_plugin_lambda_build.recipes import _run_process


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


def assert_zip_file(filename: str, base_path: str = None, files: list = None):
    zip = zipfile.ZipFile(filename)
    _list = zip.namelist()
    if files is None:
        files = []
    if base_path:
        for file_path in _list:
            assert file_path.startswith(
                base_path), f"Install directory is wrong for {file_path}"
    for file in files:
        assert file in _list, f"{file} does not exists in zip package"


CONFIGS = [
    {
        "docker_image": "public.ecr.aws/sam/build-python3.11:latest-x86_64",
        "layer_install_dir": "python",
        "layer_artifact_path": "layer.zip",
        "function_artifact_path": "function.zip"
    },
    {
        "layer_install_dir": "python",
        "layer_artifact_path": "layer.zip",
        "function_artifact_path": "function.zip"
    },
    {
        "package_artifact_path": "function.zip"
    }
]


@pytest.mark.parametrize("config", CONFIGS)
def test_build_in_container(config: dict, vars, tmp_path: Path):
    with cd(tmp_path):
        handler_file = "test_project/handler.py"
        _run_process("poetry new test-project")
        with cd(tmp_path / "test-project"):
            _run_process("poetry add requests")
            _run_process("poetry self add poetry-plugin-export")
            open(handler_file, "w").close()
            _update_pyproject_toml(
                **config
            )
            _run_process(f"{vars} poetry build-lambda")
            if "layer_artifact_path" in config:
                assert_zip_file(
                    config["layer_artifact_path"],
                    config.get("layer_install_dir")
                )
            if "function_artifact_path" in config:
                assert_zip_file(
                    config["function_artifact_path"],
                    files=[handler_file]
                )
