from __future__ import annotations

import enum
import os
import shutil
import zipfile
from functools import wraps
from tempfile import TemporaryDirectory

from poetry.console.commands.command import Command

from poetry_plugin_lambda_build.commands import (
    INSTALL_CMD_TMPL,
    INSTALL_DEPS_CMD_IN_CONTAINER_TMPL,
    INSTALL_DEPS_CMD_TMPL,
    INSTALL_IN_CONTAINER_CMD_TMPL,
    INSTALL_IN_CONTAINER_NO_DEPS_CMD_TMPL,
    INSTALL_NO_DEPS_CMD_TMPL,
)
from poetry_plugin_lambda_build.docker import (
    copy_from_container,
    copy_to_container,
    exec_run_container,
    run_container,
)
from poetry_plugin_lambda_build.parameters import ParametersContainer
from poetry_plugin_lambda_build.requirements import RequirementsExporter
from poetry_plugin_lambda_build.utils import (
    format_cmd,
    mask_string,
    remove_suffix,
    run_cmds,
    join_cmds,
)
from poetry_plugin_lambda_build.zip import create_zip_package
from poetry_plugin_lambda_build.utils import compute_checksum

CONTAINER_CACHE_DIR = "/opt/lambda/cache"
CURRENT_WORK_DIR = os.getcwd()


class BuildLambdaPluginError(Exception):
    pass


class BuildType(enum.Enum):
    IN_CONTAINER_MERGED = enum.auto()
    IN_CONTAINER_SEPARATED = enum.auto()
    MERGED = enum.auto()
    SEPARATED = enum.auto()

    @classmethod
    def get_type(cls, parameters: dict):
        layer = parameters.get("layer-artifact-path")
        function = parameters.get("function-artifact-path")
        container_img = parameters.get("docker-image")
        if container_img:
            if layer and function:
                return cls.IN_CONTAINER_SEPARATED
            else:
                return cls.IN_CONTAINER_MERGED
        elif layer and function:
            return cls.SEPARATED
        else:
            return cls.MERGED


def get_requirements(cmd: Command, parameters: ParametersContainer) -> str:
    return RequirementsExporter(
        poetry=cmd.poetry, io=cmd.io, groups=parameters.groups
    ).export()


def get_indexes(cmd: Command, parameters: ParametersContainer) -> str:
    return RequirementsExporter(
        poetry=cmd.poetry, io=cmd.io, groups=parameters.groups
    ).export_indexes()


def verify_checksum(param):
    def decorator(fun):
        @wraps(fun)
        def wrapper(self: Builder, *args, **kwargs):
            if self.parameters["no-checksum"]:
                return fun(self, *args, **kwargs)

            target = self.parameters[param]
            prefix = param.split("-", 1)[0]
            install_dir = self.parameters[f"{prefix}-install-dir"]
            is_zip = target.endswith(".zip")
            try:
                if is_zip:
                    archive = zipfile.ZipFile(target, "r")
                    prev_checksum = archive.read(
                        os.path.join(install_dir, "checksum")
                    ).decode()
                else:
                    prev_checksum = open(
                        os.path.join(target, install_dir, "checksum")
                    ).read()
            except (FileNotFoundError, KeyError):
                prev_checksum = None

            if prefix == "layer":
                curr_checksum = compute_checksum(
                    os.path.join(CURRENT_WORK_DIR, "poetry.lock")
                )
            elif prefix == "function":
                curr_checksum = compute_checksum(
                    CURRENT_WORK_DIR,
                    exclude=[
                        os.path.join(CURRENT_WORK_DIR, target),
                        os.path.join(CURRENT_WORK_DIR, target, "*"),
                        os.path.join(CURRENT_WORK_DIR, "poetry.lock"),
                    ],
                )
            else:
                curr_checksum = compute_checksum(
                    CURRENT_WORK_DIR,
                    exclude=[
                        os.path.join(CURRENT_WORK_DIR, target, "*"),
                        os.path.join(CURRENT_WORK_DIR, target),
                    ],
                )
            self.cmd.info("Checksum verification...")
            self.cmd.info(f"Previous checksum = {prev_checksum}")
            self.cmd.info(f"Current checksum = {curr_checksum}")

            if curr_checksum == prev_checksum:
                self.cmd.info(f"No changes detected in target: {target}")
                return

            retval = fun(self, *args, **kwargs)
            with TemporaryDirectory() as dir:
                checksum_file_path = os.path.join(dir, "checksum")
                with open(checksum_file_path, "w") as file:
                    file.write(curr_checksum)

                if is_zip:
                    with zipfile.ZipFile(target, "a") as zipf:
                        zipf.write(
                            checksum_file_path, os.path.join(install_dir, "checksum")
                        )
                else:
                    shutil.copyfile(
                        checksum_file_path,
                        os.path.join(CURRENT_WORK_DIR, target, install_dir, "checksum"),
                    )

            return retval

        return wrapper

    return decorator


class Builder:
    def __init__(self, cmd: Command, parameters: ParametersContainer) -> None:
        self.cmd = cmd
        self.parameters = parameters
        self._type: BuildType = BuildType.get_type(parameters)
        if self._type in (
            BuildType.IN_CONTAINER_SEPARATED,
            BuildType.IN_CONTAINER_MERGED,
        ):
            self.in_container = True
        else:
            self.in_container = False

    def format_cmd(self, string: str, **kwargs) -> tuple[list[str], str]:
        indexes = get_indexes(self.cmd, self.parameters)
        cmd = format_cmd(
            string,
            package_name=self.cmd.poetry.package.name,
            indexes=indexes,
            **kwargs,
        )

        print_safe_cmd = format_cmd(
            string,
            package_name=self.cmd.poetry.package.name,
            indexes=mask_string(" ".join(indexes)),
            **kwargs,
        )

        return cmd, print_safe_cmd

    def _build_separate_layer_in_container(
        self, requirements_path: str, layer_output_dir: str
    ):
        self.cmd.info("Running docker container...")
        with run_container(
            self.cmd, **self.parameters.get_section("docker")
        ) as container:
            copy_to_container(
                src=requirements_path, dst=f"{container.id}:/requirements.txt"
            )
            self.cmd.info("Installing requirements")

            install_deps_cmd_in_container_tmpl = join_cmds(
                self.parameters.get("pre-install-script"),
                INSTALL_DEPS_CMD_IN_CONTAINER_TMPL,
            )
            cmd, print_safe_cmd = self.format_cmd(
                install_deps_cmd_in_container_tmpl,
                output_dir=CONTAINER_CACHE_DIR,
                requirements="/requirements.txt",
            )

            exec_run_container(
                logger=self.cmd,
                container=container,
                container_cmd=cmd,
                print_safe_cmds=print_safe_cmd,
            )
            self.cmd.info(f"Coping output to {layer_output_dir}")
            copy_from_container(
                src=f"{container.id}:{CONTAINER_CACHE_DIR}/.", dst=layer_output_dir
            )

    def _create_target(self, dir: str, target: str, exclude: None | list = None):
        if target.endswith(".zip"):
            create_zip_package(
                dir=dir,
                output=target,
                exclude=exclude,
                **self.parameters.get_section("zip"),
            )
        else:
            shutil.copytree(
                dir,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*exclude) if exclude else None,
            )

    def _build_separate_layer_on_local(
        self, requirements_path: str, layer_output_dir: str
    ):
        self.cmd.info("Installing requirements")
        cmd, print_safe_cmd = self.format_cmd(
            INSTALL_DEPS_CMD_TMPL,
            output_dir=layer_output_dir,
            requirements=requirements_path,
        )

        run_cmds(cmds=cmd, print_safe_cmds=print_safe_cmd, logger=self.cmd)

    @verify_checksum("layer-artifact-path")
    def build_separate_layer_package(self):
        self.cmd.info("Building separate layer package...")
        with TemporaryDirectory() as tmp_dir:
            install_dir = self.parameters.get("layer-install-dir", "")
            layer_output_dir = os.path.join(tmp_dir, "layer-output")
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get("layer-artifact-path", "")
            )
            requirements_path = os.path.join(tmp_dir, "requirements.txt")
            layer_output_dir = os.path.join(layer_output_dir, install_dir)
            os.makedirs(layer_output_dir, exist_ok=True)

            self.cmd.info("Generating requirements file...")

            with open(requirements_path, "w") as f:
                f.write(get_requirements(self.cmd, self.parameters))

            if self.in_container:
                self._build_separate_layer_in_container(
                    requirements_path,
                    layer_output_dir,
                )
            else:
                self._build_separate_layer_on_local(
                    requirements_path,
                    layer_output_dir,
                )

            self.cmd.info(f"Building {target}...")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            self._create_target(
                dir=remove_suffix(layer_output_dir, install_dir),
                target=target,
                exclude=[requirements_path],
            )
            self.cmd.info(f"target successfully built: {target}...")

    def _build_separated_function_in_container(self, package_dir: str):
        with run_container(
            self.cmd, **self.parameters.get_section("docker"), working_dir="/"
        ) as container:
            copy_to_container(src=f"{CURRENT_WORK_DIR}/.", dst=f"{container.id}:/")

            install_in_container_no_deps_cmd_tmpl = join_cmds(
                self.parameters.get("pre-install-script"),
                INSTALL_IN_CONTAINER_NO_DEPS_CMD_TMPL,
            )

            cmd, print_safe_cmd = self.format_cmd(
                install_in_container_no_deps_cmd_tmpl, output_dir=CONTAINER_CACHE_DIR
            )

            exec_run_container(self.cmd, container, cmd, print_safe_cmd)
            copy_from_container(
                src=f"{container.id}:{CONTAINER_CACHE_DIR}/.", dst=package_dir
            )

    def _build_separated_function_on_local(self, package_dir: str):
        os.makedirs(package_dir, exist_ok=True)

        install_no_deps_cmd_tmpl = join_cmds(
            self.parameters.get("pre-install-script"), INSTALL_NO_DEPS_CMD_TMPL
        )
        cmd, print_safe_cmd = self.format_cmd(
            install_no_deps_cmd_tmpl,
            output_dir=package_dir,
        )

        run_cmds(cmds=cmd, print_safe_cmds=print_safe_cmd, logger=self.cmd)

    @verify_checksum("function-artifact-path")
    def build_separated_function_package(self):
        self.cmd.info("Building function package...")
        with TemporaryDirectory() as tmp_dir:
            install_dir = self.parameters.get("function-install-dir", "")
            package_dir = tmp_dir
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get("function-artifact-path", "")
            )
            package_dir = os.path.join(package_dir, install_dir)
            if self.in_container:
                self._build_separated_function_in_container(package_dir)
            else:
                self._build_separated_function_on_local(package_dir)

            self.cmd.info(f"Building target: {target}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            self._create_target(
                dir=remove_suffix(package_dir, install_dir),
                target=target,
            )
            self.cmd.info(f"Target successfully built: {target}...")

    def _build_package_in_container(self, package_dir: str):
        self.cmd.info("Running container...")
        with run_container(
            self.cmd, **self.parameters.get_section("docker"), working_dir="/"
        ) as container:
            self.cmd.info("Coping content")
            copy_to_container(f"{CURRENT_WORK_DIR}/.", f"{container.id}:/")

            install_in_container_cmd_tmpl = join_cmds(
                self.parameters.get("pre-install-script"), INSTALL_IN_CONTAINER_CMD_TMPL
            )
            cmd, print_safe_cmd = self.format_cmd(
                install_in_container_cmd_tmpl,
                output_dir=CONTAINER_CACHE_DIR,
            )

            exec_run_container(
                logger=self.cmd,
                container=container,
                container_cmd=cmd,
                print_safe_cmds=print_safe_cmd,
            )
            copy_from_container(
                src=f"{container.id}:{CONTAINER_CACHE_DIR}/.", dst=package_dir
            )

    def _build_package_on_local(self, package_dir: str):
        self.cmd.info("Building package on local")

        install_cmd_tmpl = join_cmds(
            self.parameters.get("pre-install-script"), INSTALL_CMD_TMPL
        )

        cmd, print_safe_cmd = self.format_cmd(install_cmd_tmpl, output_dir=package_dir)

        run_cmds(cmds=cmd, print_safe_cmds=print_safe_cmd, logger=self.cmd)

    @verify_checksum("package-artifact-path")
    def build_package(self):
        self.cmd.info("Building package...")
        with TemporaryDirectory() as tmp_dir:
            install_dir = self.parameters.get("package-install-dir", "")
            package_dir = os.path.join(tmp_dir, install_dir)
            os.makedirs(package_dir, exist_ok=True)
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get("package-artifact-path", "")
            )

            if self.in_container:
                self._build_package_in_container(package_dir)
            else:
                self._build_package_on_local(package_dir)

            os.makedirs(os.path.dirname(target), exist_ok=True)
            self._create_target(
                dir=remove_suffix(package_dir, install_dir), target=target
            )
            self.cmd.info(f"target successfully built: {target}...")

    def build(self):
        if self._type in (BuildType.IN_CONTAINER_SEPARATED, BuildType.SEPARATED):
            self.cmd.info("Building separated packages...")
            self.build_separated_function_package()
            self.build_separate_layer_package()
        elif self._type == BuildType.IN_CONTAINER_MERGED:
            self.build_package()
        else:
            self.build_package()
