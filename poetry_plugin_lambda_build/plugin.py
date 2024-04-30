import enum
import platform
from typing import Any

from cleo.application import Application
from cleo.helpers import argument
from poetry.console.commands.env_command import EnvCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from .recipes import (create_package, create_separate_layer_package,
                      create_separated_function_package)
from .utils import remove_prefix

mkdir: str =  "mkdir -p" if platform.system() == 'Windows' else "mkdir"

INSTALL_DEPS_CMD = (
    "{mkdir} {container_cache_dir} && "
    "pip install -q --upgrade pip && "
    "pip install -q -t {container_cache_dir} --no-cache-dir -r {requirements}"
)

INSTALL_NO_DEPS_CMD = (
    "{mkdir} {package_dir} && poetry run pip install"
    " --quiet -t {package_dir} --no-cache-dir --no-deps . --upgrade"
)

DEFAULT_PARAMETERS = {
    "docker_entrypoint": "/bin/sh",
    "docker_network": "host",
    "docker_options": [],
    "artifact_path": "package.zip",
    "install_no_deps_cmd": INSTALL_NO_DEPS_CMD,
    "install_deps_cmd": INSTALL_DEPS_CMD,
    "without": None,
    "only": None,
    "with": None,
}


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


ARGS = {
    "docker_image": ("The image to run", True, False, None),
    "docker_entrypoint": ("The entrypoint for the container (comma separated string)", True, False, None),
    "docker_environment": ("Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2", True, False, None),
    "docker_dns": ("Set custom DNS servers (comma separated string)", True, False, None),
    "docker_network": ("The name of the network this container will be connected to at creation time", True, False, None),
    "docker_network_disabled": ("Disable networking ex. docker_network_disabled=0", True, False, None),
    "docker_network_mode": ("Network_mode", True, False, None),
    "docker_platform": ("Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.", True, False, None),
    "package_install_dir": ("Installation directory inside zip artifact for single zip package", True, False, None),
    "layer_install_dir": ("Installation directory inside zip artifact for layer zip package", True, False, None),
    "function_install_dir": ("Installation directory inside zip artifact for function zip package", True, False, None),
    "install_dir": ("Installation directory inside zip artifact for zip package (not function layer separation)", True, False, None),
    "package_artifact_path": ("Output package path", True, False, None),
    "layer_artifact_path": ("Output layer package path", True, False, None),
    "function_artifact_path": ("Output function package path", True, False, None),
    "only": ("The only dependency groups to include", True, False, None),
    "without": ("The dependency groups to ignore", True, False, None),
    "with": ("The optional dependency groups to include", True, False, None),
    "install_deps_cmd": (f"Install dependencies command. Executed during installation of dependencies layer, by default: {INSTALL_DEPS_CMD}", True, False, None),
    "install_no_deps_cmd": (f"Install without dependencies command. Executed during installation of function, by default: {INSTALL_NO_DEPS_CMD}", True, False, None),
}

ARGS_SECTIONS = ("layer", "function", "docker", "artifacts")


class ParametersContainer(dict):
    args = ARGS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update(DEFAULT_PARAMETERS)

    def put(self, key: Any, value: Any) -> None:
        prev_value = self.get(key)
        if isinstance(prev_value, list):
            self[key].append(value)
        else:
            self[key] = value
        return

    def get_section(self, section: str) -> dict:
        result = {}
        for k in self:
            if k.startswith(section):
                key = remove_prefix(k, section+"_")
                result[key] = self[k]
        return result


class BuildLambdaCommand(EnvCommand):
    name = "build-lambda"
    description = "Execute to build lambda lambda artifacts"

    arguments = [
        argument(name, *params) for name, params in ARGS.items()
    ]

    def _get_parameters(self) -> ParametersContainer:
        pyproject_data = self.poetry.pyproject.data
        container = ParametersContainer()
        for token in filter(lambda token: any([token.startswith(f"{arg}=") for arg in ARGS]), self.io.input._tokens[1:]):
            key, value = token.strip().split("=")
            container.put(key, value)

        try:
            plugin_conf = pyproject_data["tool"]["poetry-plugin-lambda-build"]
        except KeyError:
            plugin_conf = None

        if plugin_conf:
            for k in plugin_conf:
                container.put(k, plugin_conf[k])
        return container

    def handle(self) -> Any:
        parameters: ParametersContainer = self._get_parameters()
        _type: BuildType = BuildType.get_type(parameters)
        if _type == BuildType.IN_CONTAINER_SEPARATED:
            self.line("Building separated packages in container...", style="info")
            create_separated_function_package(self, parameters)
            create_separate_layer_package(self, parameters)
        elif _type == BuildType.SEPARATED:
            self.line("Building separated packages on local...", style="info")
            create_separate_layer_package(self, parameters, in_container=False)
            create_separated_function_package(self, parameters)
        elif _type == BuildType.IN_CONTAINER_MERGED:
            create_package(self, parameters, in_container=True)
        else:
            create_package(self, parameters, in_container=False)
        self.line("\n✨ Done!")


def factory() -> BuildLambdaCommand:
    return BuildLambdaCommand()


class LambdaPlugin(ApplicationPlugin):
    def activate(self, application: Application, *args: Any, **kwargs: Any) -> None:
        application.command_loader.register_factory("build-lambda", factory)
