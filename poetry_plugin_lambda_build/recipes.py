import os
import subprocess
from tempfile import TemporaryDirectory
from typing import ByteString

from poetry.console.commands.env_command import EnvCommand

from .docker import copy_from, copy_to, run_container
from .utils import remove_suffix
from .zip import create_zip_package


class BuildLambdaPluginError(Exception):
    pass


CONTAINER_CACHE_DIR = "/opt/lambda/cache"
CURRENT_WORK_DIR = os.getcwd()


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
    self: EnvCommand, parameters: dict, in_container: bool = True
):
    with TemporaryDirectory() as tmp_dir:
        install_dir = parameters.get("layer_install_dir", "")
        layer_output_dir = os.path.join(tmp_dir, "layer_output")

        target = os.path.join(
            CURRENT_WORK_DIR, parameters.get("layer_artifact_path", "")
        )
        requirements_path = os.path.join(tmp_dir, "requirements.txt")

        poetry_export_cmd = "poetry export --format=requirements.txt"

        if parameters["without"]:
            poetry_export_cmd += f" --without={parameters['without']}"

        if parameters["with"]:
            poetry_export_cmd += f" --with={parameters['with']}"

        if parameters["only"]:
            poetry_export_cmd += f" --only={parameters['only']}"

        if install_dir:
            layer_output_dir = os.path.join(layer_output_dir, install_dir)

        self.line("Generating requirements file...", style="info")
        self.line(f"Executing: {poetry_export_cmd}", style="debug")

        output = _run_process(self, poetry_export_cmd)

        with open(requirements_path, "w") as f:
            f.write(output.decode("utf-8"))

        if in_container:
            with run_container(self, **parameters.get_section("docker")) as container:
                copy_to(requirements_path, f"{container.id}:/requirements.txt")
                self.line("Installing requirements", style="info")
                install_deps_cmd = parameters["install_deps_cmd"].format(
                    container_cache_dir=CONTAINER_CACHE_DIR,
                    requirements="/requirements.txt",
                )
                result = container.exec_run(
                    f'sh -c "{install_deps_cmd}"', stream=True)
                for line in result.output:
                    self.line(line.strip().decode("utf-8"), style="info")
                self.line(f"Coping output to {layer_output_dir}", style="info")
                os.makedirs(layer_output_dir, exist_ok=True)
                copy_from(f"{container.id}:{CONTAINER_CACHE_DIR}/.",
                          layer_output_dir)
        else:
            install_deps_cmd = parameters["install_deps_cmd"].format(
                container_cache_dir=layer_output_dir, requirements=requirements_path
            )

            self.line("Installing requirements", style="info")
            self.line(f"Executing: {install_deps_cmd}", style="debug")
            _run_process(self, install_deps_cmd)

        self.line(f"Building {target}...", style="info")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            remove_suffix(layer_output_dir, install_dir)
            if install_dir
            else layer_output_dir,
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")


def create_separated_function_package(self: EnvCommand, parameters: dict):
    with TemporaryDirectory() as tmp_dir:
        install_dir = parameters.get("function_install_dir", "")
        package_dir = tmp_dir
        target = os.path.join(
            CURRENT_WORK_DIR, parameters.get("function_artifact_path", "")
        )

        package_dir = os.path.join(package_dir, install_dir)
        self.line("Building function package...", style="info")

        install_cmd = parameters["install_no_deps_cmd"].format(
            package_dir=package_dir)

        self.line(f"Executing: {install_cmd}", style="debug")

        _run_process(self, install_cmd)

        self.line(f"Building target: {target}", style="info")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            remove_suffix(package_dir, install_dir),
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")


def create_package(self: EnvCommand, parameters: dict, in_container: bool = True):
    current_working_directory = os.getcwd()
    with TemporaryDirectory() as package_dir:
        install_dir = parameters.get("install_dir", "")

        if install_dir:
            package_dir = os.path.join(package_dir, install_dir)

        target = os.path.join(
            current_working_directory, parameters.get("artifact_path", "")
        )
        if in_container:
            self.line("Building package in container", style="info")
            with run_container(self, **parameters.get_section("docker")) as container:

                for config in parameters["config"]:
                    result = container.exec_run(
                        f'poetry config {config}', stream=True)
                    for line in result.output:
                        self.line(line.strip().decode("utf-8"), style="info")

                cmd = parameters["install_package_cmd"].format(
                    package_dir=package_dir)
                self.line(f"Executing: {cmd}", style="debug")
                result = container.exec_run(f'sh -c "{cmd}"', stream=True)

                for line in result.output:
                    self.line(line.strip().decode("utf-8"), style="info")

                copy_from(f"{container.id}:{package_dir}/.", package_dir)
        else:
            self.line("Building package on local", style="info")
            cmd = parameters["install_package_cmd"].format(
                package_dir=package_dir)
            self.line(f"Executing: {cmd}", style="debug")
            _run_process(self, cmd)

        os.makedirs(os.path.dirname(target), exist_ok=True)
        create_zip_package(
            remove_suffix(
                package_dir, install_dir) if install_dir else package_dir,
            target,
        )
        self.line(f"target successfully built: {target}...", style="info")
