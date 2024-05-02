import enum
import os
from tempfile import TemporaryDirectory

from poetry.console.commands.command import Command

from poetry_plugin_lambda_build.commands import (
    BUILD_N_INSTALL_CMD_TMPL, BUILD_N_INSTALL_NO_DEPS_CMD_TMPL,
    BUILD_PACKAGE_CMD, INSTALL_DEPS_CMD_TMPL, INSTALL_WHL_CMD_TMPL,
    INSTALL_WHL_NO_DEPS_CMD_TMPL)
from poetry_plugin_lambda_build.docker import (copy_from, copy_to,
                                               exec_run_container,
                                               run_container)
from poetry_plugin_lambda_build.parameters import ParametersContainer
from poetry_plugin_lambda_build.requirements import RequirementsExporter
from poetry_plugin_lambda_build.utils import (format_str, mask_string,
                                              remove_suffix, run_python_cmd)
from poetry_plugin_lambda_build.zip import create_zip_package

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
        layer = parameters.get("layer_artifact_path")
        function = parameters.get("function_artifact_path")
        container_img = parameters.get("docker_image")
        if container_img:
            if layer and function:
                return cls.IN_CONTAINER_SEPARATED
            else:
                return cls.IN_CONTAINER_MERGED
        else:
            if layer and function:
                return cls.SEPARATED
            else:
                return cls.MERGED


def get_requirements(self: Command, parameters: ParametersContainer) -> str:
    return RequirementsExporter(
        poetry=self.poetry,
        io=self.io,
        groups=parameters.groups
    ).export()


def get_indexes(self: Command, parameters: ParametersContainer) -> str:
    return RequirementsExporter(
        poetry=self.poetry,
        io=self.io,
        groups=parameters.groups
    ).export_indexes()


class Builder:
    def __init__(self, cmd: Command, parameters: ParametersContainer) -> None:
        self.cmd = cmd
        self.parameters = parameters
        self._type: BuildType = BuildType.get_type(parameters)
        if self._type in (BuildType.IN_CONTAINER_SEPARATED, BuildType.IN_CONTAINER_MERGED):
            self.in_container = True
        else:
            self.in_container = False

    def format_str(self, string: str, **kwargs) -> tuple[str, str]:
        return format_str(
            string,
            package_name=self.cmd.poetry.package.name,
            indexes=get_indexes(self.cmd, self.parameters),
            **kwargs
        ), format_str(
            string,
            package_name=self.cmd.poetry.package.name,
            indexes=mask_string(get_indexes(self.cmd, self.parameters)),
            **kwargs
        )

    def create_separate_layer_package(self):
        self.cmd.info("Building separate layer package...")
        with TemporaryDirectory() as tmp_dir:
            install_dir = self.parameters.get("layer_install_dir", "")
            layer_output_dir = os.path.join(tmp_dir, "layer_output")
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get(
                    "layer_artifact_path", "")
            )
            requirements_path = os.path.join(tmp_dir, "requirements.txt")
            layer_output_dir = os.path.join(layer_output_dir, install_dir)
            os.makedirs(layer_output_dir, exist_ok=True)

            self.cmd.info("Generating requirements file...")

            with open(requirements_path, "w") as f:
                f.write(get_requirements(self.cmd, self.parameters))

            if self.in_container:
                self.cmd.info("Running docker container...")
                with run_container(self.cmd, **self.parameters.get_section("docker")) as container:
                    copy_to(
                        src=requirements_path,
                        dst=f"{container.id}:/requirements.txt"
                    )
                    self.cmd.info("Installing requirements")
                    cmd, print_safe_cmd = self.format_str(
                        INSTALL_DEPS_CMD_TMPL,
                        output_dir=CONTAINER_CACHE_DIR,
                        requirements="/requirements.txt",
                    )
                    self.cmd.debug(
                        f"Executing: {print_safe_cmd}")
                    exec_run_container(
                        logger=self.cmd,
                        container=container,
                        entrypoint=self.parameters["docker_entrypoint"],
                        container_cmd=cmd,
                    )
                    self.cmd.info(
                        f"Coping output to {layer_output_dir}")
                    copy_from(
                        src=f"{container.id}:{CONTAINER_CACHE_DIR}/.",
                        dst=layer_output_dir
                    )
            else:
                self.cmd.info("Installing requirements")
                cmd, print_safe_cmd = self.format_str(
                    INSTALL_DEPS_CMD_TMPL,
                    output_dir=layer_output_dir,
                    requirements=requirements_path,
                )
                self.cmd.info(f"Executing: {print_safe_cmd}")
                run_python_cmd("-m", cmd)

            self.cmd.info(f"Building {target}...")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            create_zip_package(
                dir=remove_suffix(layer_output_dir, install_dir),
                output=target,
                exclude=[requirements_path],
                **self.parameters.get_section("zip")
            )
            self.cmd.info(
                f"target successfully built: {target}...")

    def create_separated_function_package(self):
        self.cmd.info("Building function package...")
        with TemporaryDirectory() as tmp_dir:
            install_dir = self.parameters.get("function_install_dir", "")
            package_dir = tmp_dir
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get(
                    "function_artifact_path", "")
            )

            package_dir = os.path.join(package_dir, install_dir)
            if self.in_container:
                with run_container(self.cmd, **self.parameters.get_section("docker"), working_dir="/") as container:
                    copy_to(
                        src=f"{CURRENT_WORK_DIR}/.",
                        dst=f"{container.id}:/"
                    )

                    cmd, print_safe_cmd = self.format_str(
                        BUILD_N_INSTALL_NO_DEPS_CMD_TMPL,
                        output_dir=CONTAINER_CACHE_DIR
                    )

                    self.cmd.info(
                        f"Executing: {print_safe_cmd}")
                    exec_run_container(
                        self.cmd, container, self.parameters["docker_entrypoint"], cmd)
                    copy_from(
                        src=f"{container.id}:{CONTAINER_CACHE_DIR}/.",
                        dst=package_dir
                    )
            else:
                cmd, print_safe_cmd = self.format_str(BUILD_PACKAGE_CMD)
                os.makedirs(package_dir, exist_ok=True)
                self.cmd.debug(f"Executing: {print_safe_cmd}")
                run_python_cmd("-m", cmd, logger=self.cmd)
                cmd, print_safe_cmd = self.format_str(
                    INSTALL_WHL_NO_DEPS_CMD_TMPL,
                    output_dir=package_dir,
                )
                self.cmd.debug(f"Executing: {print_safe_cmd}")
                run_python_cmd("-m", cmd, logger=self.cmd)

            self.cmd.info(f"Building target: {target}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            create_zip_package(
                dir=remove_suffix(package_dir, install_dir),
                output=target,
                exclude=[],
                **self.parameters.get_section("zip")
            )
            self.cmd.info(
                f"Target successfully built: {target}...")

    def create_package(self):
        self.cmd.info("Building package...")
        with TemporaryDirectory() as package_dir:
            install_dir = self.parameters.get("install_dir", "")
            package_dir = os.path.join(package_dir, install_dir)
            os.makedirs(package_dir, exist_ok=True)
            target = os.path.join(
                CURRENT_WORK_DIR, self.parameters.get(
                    "package_artifact_path", "")
            )

            if self.in_container:
                self.cmd.info("Running container...")
                with run_container(self.cmd, **self.parameters.get_section("docker"), working_dir="/") as container:
                    self.cmd.info("Coping content")
                    copy_to(f"{CURRENT_WORK_DIR}/.", f"{container.id}:/")

                    cmd, print_safe_cmd = self.format_str(
                        BUILD_N_INSTALL_CMD_TMPL,
                        output_dir=CONTAINER_CACHE_DIR,
                    )

                    self.cmd.debug(f"Executing: {print_safe_cmd}")

                    exec_run_container(
                        logger=self.cmd,
                        container=container,
                        entrypoint=self.parameters["docker_entrypoint"],
                        container_cmd=cmd
                    )
                    copy_from(
                        src=f"{container.id}:{CONTAINER_CACHE_DIR}/.",
                        dst=package_dir
                    )
            else:
                self.cmd.info("Building package on local")
                cmd, print_safe_cmd = self.format_str(
                    BUILD_PACKAGE_CMD
                )
                self.cmd.debug(f"Executing: {print_safe_cmd}")
                run_python_cmd("-m", cmd, logger=self.cmd)
                cmd, print_safe_cmd = self.format_str(
                    INSTALL_WHL_CMD_TMPL,
                    output_dir=package_dir
                )
                self.cmd.debug(
                    f"Executing: {print_safe_cmd}")
                run_python_cmd("-m", cmd, logger=self.cmd)

            os.makedirs(os.path.dirname(target), exist_ok=True)
            create_zip_package(
                dir=remove_suffix(package_dir, install_dir),
                output=target,
                exclude=[],
                **self.parameters.get_section("zip")
            )
            self.cmd.info(
                f"target successfully built: {target}...")

    def build(self):
        if self._type in (BuildType.IN_CONTAINER_SEPARATED, BuildType.SEPARATED):
            self.cmd.info("Building separated packages...")
            self.create_separated_function_package()
            self.create_separate_layer_package()
        elif self._type == BuildType.IN_CONTAINER_MERGED:
            self.create_package()
        else:
            self.create_package()
