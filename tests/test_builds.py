from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import pytest

from poetry_plugin_lambda_build.utils import cd
from tests.utils import (
    assert_file_exists_in_dir,
    assert_file_exists_in_zip,
    assert_file_not_exists_in_dir,
    assert_file_not_exists_in_zip,
    run_poetry_cmd,
    update_pyproject_toml,
)


@pytest.fixture(scope="session", autouse=True)
def env_vars():
    if platform.system() == "Darwin":
        user = os.environ["USER"]
        os.environ["DOCKER_HOST"] = f"unix:///Users/{user}/.docker/run/docker.sock"
    yield


PYTHON_VER = f"{sys.version_info[0]}.{sys.version_info[1]}"
DOCKER_IMG = f"public.ecr.aws/sam/build-python{PYTHON_VER}:latest-x86_64"

ZIP_BUILDS_PARAMS = {
    "layer function separated in container": (
        {
            "docker-image": DOCKER_IMG,
            "layer-install-dir": "python",
            "layer-artifact-path": "layer.zip",
            "function-artifact-path": "function.zip",
        },
        {},
        [
            lambda: assert_file_exists_in_zip("layer.zip", "python"),
            lambda: assert_file_not_exists_in_zip(
                "layer.zip", files=["python/requirements.txt"]
            ),
            lambda: assert_file_exists_in_zip(
                "function.zip", files=["test_project/handler.py"]
            ),
        ],
    ),
    "layer function separated on local": (
        {
            "layer-install-dir": "python",
            "layer-artifact-path": "layer.zip",
            "function-artifact-path": "function.zip",
        },
        {},
        [
            lambda: assert_file_exists_in_zip("layer.zip", "python"),
            lambda: assert_file_not_exists_in_zip(
                "layer.zip", files=["python/requirements.txt"]
            ),
            lambda: assert_file_exists_in_zip(
                "function.zip", files=["test_project/handler.py"]
            ),
        ],
    ),
    "all in one on local": (
        {"package-artifact-path": "function.zip", "package-install-dir": "python"},
        {},
        [
            lambda: assert_file_exists_in_zip(
                "function.zip", files=["python/test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_zip(
                "function.zip", files=["python/requirements.txt"]
            ),
        ],
    ),
    "all in one, docker img provided in cli": (
        {"package-artifact-path": "function.zip", "package-install-dir": "python"},
        {
            "docker-image": DOCKER_IMG,
        },
        [
            lambda: assert_file_exists_in_zip(
                "function.zip", files=["python/test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_zip(
                "function.zip", files=["python/requirements.txt"]
            ),
        ],
    ),
    "all in one, without dev": (
        {"package-artifact-path": "function.zip", "without": "test"},
        {},
        [
            lambda: assert_file_exists_in_zip(
                "function.zip", files=["test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_zip(
                "function.zip", files=["pytest/__init__.py", "*requirements*"]
            ),
        ],
    ),
}

DIR_BUILDS_PARAMS = {
    "layer function separated in container": (
        {
            "docker-image": DOCKER_IMG,
            "layer-install-dir": "python",
            "layer-artifact-path": "layer",
            "function-artifact-path": "function",
        },
        {},
        [
            lambda: assert_file_exists_in_dir("layer", "python"),
            lambda: assert_file_not_exists_in_dir(
                "layer", files=["python/requirements.txt"]
            ),
            lambda: assert_file_exists_in_dir(
                "function", files=["test_project/handler.py"]
            ),
        ],
    ),
    "layer function separated on local": (
        {
            "layer-install-dir": "python",
            "layer-artifact-path": "layer",
            "function-artifact-path": "function",
        },
        {},
        [
            lambda: assert_file_exists_in_dir("layer", "python"),
            lambda: assert_file_not_exists_in_dir(
                "layer", files=["python/requirements.txt"]
            ),
            lambda: assert_file_exists_in_dir(
                "function", files=["test_project/handler.py"]
            ),
        ],
    ),
    "all in one on local": (
        {"package-artifact-path": "function", "package-install-dir": "python"},
        {},
        [
            lambda: assert_file_exists_in_dir(
                "function", files=["python/test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_dir(
                "function", files=["python/requirements.txt"]
            ),
        ],
    ),
    "all in one, docker img provided in cli": (
        {"package-artifact-path": "function", "package-install-dir": "python"},
        {
            "docker-image": DOCKER_IMG,
        },
        [
            lambda: assert_file_exists_in_dir(
                "function", files=["python/test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_dir(
                "function", files=["python/requirements.txt"]
            ),
        ],
    ),
    "all in one, without dev": (
        {"package-artifact-path": "function", "without": "test"},
        {},
        [
            lambda: assert_file_exists_in_dir(
                "function", files=["test_project/handler.py"]
            ),
            lambda: assert_file_not_exists_in_dir(
                "function", files=["pytest/__init__.py", "*requirements*"]
            ),
        ],
    ),
}


@pytest.mark.parametrize(
    "config,args,assert_files",
    list(ZIP_BUILDS_PARAMS.values()),
    ids=list(ZIP_BUILDS_PARAMS.keys()),
)
def test_zip_builds(config: dict, args: dict, assert_files: list, tmp_path: Path):
    with cd(tmp_path):
        handler_file = "src/test_project/handler.py"
        assert run_poetry_cmd("new", "test-project") == 0
        with cd(tmp_path / "test-project"):
            assert run_poetry_cmd("add", "requests") == 0
            assert run_poetry_cmd("add", "pytest", "--group=test") == 0
            open(handler_file, "wb").close()

            if PYTHON_VER == "3.8":
                config["pre-install-script"] = (
                    "python3 -m pip install urllib3<2.0 -U -q"
                )

            if config:
                update_pyproject_toml(**config)
            arguments = " ".join(f"{k}={v}" for k, v in args.items())
            assert run_poetry_cmd("build-lambda", arguments, "-vv") == 0
            for files_assertion in assert_files:
                files_assertion()


@pytest.mark.parametrize(
    "config,args,assert_files",
    list(DIR_BUILDS_PARAMS.values()),
    ids=list(DIR_BUILDS_PARAMS.keys()),
)
def test_dir_builds(config: dict, args: dict, assert_files: list, tmp_path: Path):
    with cd(tmp_path):
        handler_file = "src/test_project/handler.py"
        assert run_poetry_cmd("new", "test-project") == 0
        with cd(tmp_path / "test-project"):
            assert run_poetry_cmd("add", "requests") == 0
            assert run_poetry_cmd("add", "pytest", "--group=test") == 0
            open(handler_file, "w").close()

            if PYTHON_VER == "3.8":
                config["pre-install-script"] = (
                    "python3 -m pip install urllib3<2.0 -U -q"
                )

            if config:
                update_pyproject_toml(**config)
            arguments = " ".join(f"{k}={v}" for k, v in args.items())
            assert run_poetry_cmd("build-lambda", arguments, "-v") == 0
            for files_assertion in assert_files:
                files_assertion()
