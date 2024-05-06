import os
import platform
import zipfile
from pathlib import Path

import pytest

from poetry_plugin_lambda_build.utils import cd, run_python_cmd


def run_poetry_cmd(
    *args: list[str]
) -> int:
    return run_python_cmd("-m", "poetry", *args)


@pytest.fixture(scope="session", autouse=True)
def env_vars():
    if platform.system() == "Darwin":
        user = os.environ["USER"]
        os.environ["DOCKER_HOST"] = f"unix:///Users/{user}/.docker/run/docker.sock"
    yield


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


DOCKER_IMG = "public.ecr.aws/sam/build-python3.11:latest-x86_64"

PARAMS = [
    (
        {
            "docker_image": DOCKER_IMG,
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
            "package_artifact_path": "function.zip",
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
            "package_artifact_path": "function.zip",
            "install_dir": "python"
        },
        {
            "docker_image": DOCKER_IMG,
        },
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
            "package_artifact_path": "function.zip",
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
                files=["pytest/__init__.py", "*requirements*"]
            )
        ]
    )
]


@pytest.mark.parametrize("config,args,assert_files", PARAMS)
def test_build_in_container(config: dict, args: dict, assert_files: list, tmp_path: Path):
    with cd(tmp_path):
        handler_file = "test_project/handler.py"
        assert run_poetry_cmd("new test-project") == 0
        with cd(tmp_path / "test-project"):
            assert run_poetry_cmd("add requests") == 0
            assert run_poetry_cmd("add pytest --group=test") == 0
            assert run_poetry_cmd("self add poetry-plugin-export") == 0
            open(handler_file, "w").close()
            if config:
                _update_pyproject_toml(
                    **config
                )
            arguments = " ".join(f'{k}={v}' for k, v in args.items())
            assert run_poetry_cmd(f"build-lambda {arguments} -v") == 0
            for files_assertion in assert_files:
                files_assertion()
