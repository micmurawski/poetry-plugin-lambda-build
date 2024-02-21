import os
import subprocess
from tempfile import TemporaryDirectory
from typing import ByteString

from poetry.console.commands.env_command import EnvCommand

from .docker import copy_from, copy_to, run_container
from .utils import get_path
from .zip import create_zip_package


class BuildLambdaPluginError(Exception):
    pass


CONTAINER_CACHE_DIR = "/opt/lambda/cache"
CURRENT_WORK_DIR = os.getcwd()

INSTALL_DEPS_CMD = (
    "mkdir -p {container_cache_dir} && "
    "pip install -q --upgrade pip && "
    "pip install -q -t {container_cache_dir} --no-cache-dir -r {requirements}"
)

INSTALL_NO_DEPS_CMD = (
    "mkdir -p {package_dir} && poetry run pip install"
    " --quiet -t {package_dir} --no-cache-dir --no-deps . --upgrade"
)

INSTALL_PACKAGE_CMD = (
    "mkdir -p {package_dir} && "
    "pip install poetry --quiet --upgrade pip && "
    "poetry build --quiet && "
    "poetry run pip install --quiet -t {package_dir} --no-cache-dir dist/*.whl --upgrade"
)


def _run_process(self: EnvCommand, cmd: str) -> ByteString:
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, err = process.communicate()
    if process.returncode == 0:
        self.line_error(err.decode("utf-8"), style="warning")
        return output
    elif process.returncode == 1:
        self.line_error(err.decode("utf-8"), style="error")

    raise BuildLambdaPluginError(output.decode("utf-8"))


def create_separate_layer_package(
    self: EnvCommand, options: dict, in_container: bool = True
):
    with TemporaryDirectory() as tmp_dir:
        without = options["without"]
        install_dir = get_path(options, "layer.install_dir")
        layer_output_dir = os.path.join(tmp_dir, "layer_output")

        target = os.path.join(
            CURRENT_WORK_DIR, get_path(options, "layer.artifact_name")
        )
        requirements_path = os.path.join(tmp_dir, "requirements.txt")

        poetry_export_cmd = "poetry export --format=requirements.txt"
        if without:
            poetry_export_cmd.append(f"--without={without}")

        if install_dir:
            layer_output_dir = os.path.join(layer_output_dir, install_dir)

        self.line("Generating requirements file...", style="info")
        self.line(f"Executing: {poetry_export_cmd}", style="debug")
        output = _run_process(self, poetry_export_cmd)

        with open(requirements_path, "w") as f:
            f.write(output.decode("utf-8"))

        if in_container:
            with run_container(self, **options["docker"]) as container:
                copy_to(requirements_path, f"{container.id}:/requirements.txt")
                self.line("Installing requirements", style="info")
                install_deps_cmd = INSTALL_DEPS_CMD.format(
                    container_cache_dir=CONTAINER_CACHE_DIR,
                    requirements="/requirements.txt",
                )
                result = container.exec_run(f'sh -c "{install_deps_cmd}"', stream=True)
                for line in result.output:
                    self.line(line.strip().decode("utf-8"), style="info")
                self.line(f"Coping output to {layer_output_dir}", style="info")
                os.makedirs(layer_output_dir, exist_ok=True)
                copy_from(f"{container.id}:{CONTAINER_CACHE_DIR}/.", layer_output_dir)
        else:
            install_deps_cmd = INSTALL_DEPS_CMD.format(
                container_cache_dir=layer_output_dir, requirements=requirements_path
            )

            self.line("Installing requirements", style="info")
            self.line(f"Executing: {install_deps_cmd}", style="debug")
            _run_process(self, install_deps_cmd)

        self.line(f"Building {target}...", style="info")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            layer_output_dir.removesuffix(install_dir)
            if install_dir
            else layer_output_dir,
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")


def create_separated_handler_package(self: EnvCommand, options: dict):
    with TemporaryDirectory() as tmp_dir:
        install_dir = get_path(options, "handler.install_dir")
        package_dir = tmp_dir
        target = os.path.join(
            CURRENT_WORK_DIR, get_path(options, "handler.artifact_name")
        )

        if install_dir:
            package_dir = os.path.join(package_dir, install_dir)
        self.line("Building handler package...", style="info")

        install_cmd = INSTALL_NO_DEPS_CMD.format(package_dir=package_dir)

        self.line(f"Executing: {install_cmd}", style="debug")

        _run_process(self, install_cmd)

        self.line(f"Building target: {target}", style="info")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            package_dir.removesuffix(install_dir) if install_dir else package_dir,
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")


def create_package(self: EnvCommand, options: dict, in_container: bool = True):
    current_working_directory = os.getcwd()
    with TemporaryDirectory() as package_dir:
        install_dir = get_path(options, "install_dir")

        if install_dir:
            package_dir = os.path.join(package_dir, install_dir)

        target = os.path.join(
            current_working_directory, get_path(options, "artifact_name")
        )
        if in_container:
            self.line("Building package in container", style="info")
            with run_container(self, **options["docker"]) as container:
                cmd = INSTALL_PACKAGE_CMD.format(package_dir=package_dir)
                self.line(f"Executing: {cmd}", style="debug")
                result = container.exec_run(f'sh -c "{cmd}"', stream=True)

                for line in result.output:
                    self.line(line.strip().decode("utf-8"), style="info")

                copy_from(f"{container.id}:{package_dir}/.", package_dir)
        else:
            self.line("Building package on local", style="info")
            cmd = INSTALL_PACKAGE_CMD.format(package_dir=package_dir)
            self.line(f"Executing: {cmd}", style="debug")
            _run_process(self, cmd)

        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            package_dir.removesuffix(install_dir) if install_dir else package_dir,
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")
