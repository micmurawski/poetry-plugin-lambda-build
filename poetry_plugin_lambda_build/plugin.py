import enum
from collections import defaultdict
from typing import Any

from cleo.application import Application
from cleo.helpers import argument
from poetry.console.commands.env_command import EnvCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from .recipes import (create_package, create_separate_layer_package,
                      create_separated_function_package)
from .utils import get_path, merge_options


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

DEFAULT_OPTIONS = {
    "docker": {
        "env": None,
        "entrypoint": "/bin/sh",
        "dns": None,
        "network": "host",
        "options": [],
    },
    "layer": {
        "artifact_path": None,
        "install_dir": None,
    },
    "function": {
        "artifact_path": None,
        "install_dir": None,
    },
    "artifacts": {"path": "artifacts"},
    "without": None,
    "only": None,
    "with": None,
    "install_dir": None,
    "artifact_path": "package.zip",
    "install_package_cmd": INSTALL_PACKAGE_CMD,
    "install_no_deps_cmd": INSTALL_NO_DEPS_CMD,
    "install_deps_cmd": INSTALL_DEPS_CMD
}


class BuildType(enum.Enum):
    IN_CONTAINER_MERGED = enum.auto()
    IN_CONTAINER_SEPARATED = enum.auto()
    MERGED = enum.auto()
    SEPARATED = enum.auto()

    @classmethod
    def get_type(cls, options: dict):
        layer = get_path(options, "layer.artifact_path")
        function = get_path(options, "function.artifact_path")
        container_img = get_path(options, "docker.image")
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


ARGS = [
    ("docker_image", "The image to run"),
    ("docker_entrypoint", "The entrypoint for the container (comma separated string)"),
    ("docker_environment", "Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2"),
    ("docker_dns", "Set custom DNS servers (comma separated string)"),
    ("docker_network", "The name of the network this container will be connected to at creation time"),
    ("docker_network_disabled", "Disable networking ex. docker_network_disabled=0"),
    ("docker_network_mode", "Network_mode"),
    ("docker_platform",
     "Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image."),
    ("package_install_dir",
     "Installation directory inside zip artifact for single zip package"),
    ("layer_install_dir",
     "Installation directory inside zip artifact for layer zip package"),
    ("function_install_dir",
     "Installation directory inside zip artifact for function zip package"),
    ("package_artifact_path", "Output package path"),
    ("layer_artifact_path", "Output layer package path"),
    ("function_artifact_path", "Output function package path"),
    ("only", "The only dependency groups to include"),
    ("without", "The dependency groups to ignore"),
    ("with", "The optional dependency groups to include"),
    ("install_deps_cmd",
     f"Install dependencies command. Executed during installation of dependencies layer, by default: {INSTALL_DEPS_CMD}"),
    ("install_no_deps_cmd",
     f"Install without dependencies command. Executed during installation of function, by default: {INSTALL_NO_DEPS_CMD}"),
    ("install_package_cmd",
     f"Install package command. Executed during installation of package without function-layer separation, by default: {INSTALL_PACKAGE_CMD}")
]


class BuildLambdaCommand(EnvCommand):
    name = "build-lambda"
    description = "Execute to build lambda lambda artifacts"

    arguments = [
        argument(*arg, optional=True, multiple=False) for arg in ARGS
    ]

    def _get_options(self) -> Any:
        options = defaultdict(dict)
        options.update(DEFAULT_OPTIONS)
        override_options = defaultdict(dict)
        _missed_args = {}

        pyproject_data = self.poetry.pyproject.data
        # Gather override args
        for arg in ARGS:
            arg_name = arg[0]
            _argument = self.argument(arg_name) or _missed_args.get(arg_name)
            if _argument:
                
                if arg_name not in _argument:
                    key = _argument.split("=", 1)[0]
                    _missed_args[key] = _argument
                    continue

                try:
                    key, value = _argument.split("=", 1)
                    
                    if "_" in key:
                        prefix, name = key.split("_", 1)
                        override_options[prefix][name] = value
                    else:
                        override_options[key] = value
                    
                except ValueError as e:
                    raise Exception(
                        f"Argument {arg_name} has wrong value: {_argument}", e
                    ) from e

        pyproject_data = self.poetry.pyproject.data
        prefixes = ["layer", "function", "docker", "artifacts"]
        plugin_conf = get_path(
            pyproject_data, "tool.poetry-plugin-lambda-build"
        )
        if plugin_conf:
            for k in plugin_conf:
                for prefix in prefixes:
                    if k.startswith(prefix):
                        arg = k.removeprefix(prefix + "_")
                        options[prefix][arg] = plugin_conf[k]

        options = merge_options(options, override_options)
        return options

    def handle(self) -> Any:
        options: dict = self._get_options()
        _type: BuildType = BuildType.get_type(options)
        if _type == BuildType.IN_CONTAINER_SEPARATED:
            self.line("Building separated packages in container...", style="info")
            create_separated_function_package(self, options)
            create_separate_layer_package(self, options)
        elif _type == BuildType.SEPARATED:
            self.line("Building separated packages on local...", style="info")
            create_separate_layer_package(self, options, in_container=False)
            create_separated_function_package(self, options)
        elif _type == BuildType.IN_CONTAINER_MERGED:
            create_package(self, options, in_container=True)
        else:
            create_package(self, options, in_container=False)
        self.line("\n✨ Done!")


def factory() -> BuildLambdaCommand:
    return BuildLambdaCommand()


class LambdaPlugin(ApplicationPlugin):
    def activate(self, application: Application, *args: Any, **kwargs: Any) -> None:
        application.command_loader.register_factory("build-lambda", factory)
