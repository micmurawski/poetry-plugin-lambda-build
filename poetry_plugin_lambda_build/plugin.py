import enum
from collections import defaultdict
from typing import Any

from cleo.application import Application
from cleo.helpers import argument
from poetry.console.commands.env_command import EnvCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from .recipes import (create_package, create_separate_layer_package,
                      create_separated_handler_package)
from .utils import get_path, merge_options

DEFAULT_OPTIONS = {
    "docker": {
        "env": None,
        "entrypoint": "/bin/sh",
        "dns": None,
        "network": "host",
        "options": [],
    },
    "layer": {
        "artifact_name": None,
        "install_dir": None,
    },
    "handler": {
        "artifact_name": None,
        "install_dir": None,
    },
    "artifacts": {"path": "artifacts"},
    "without": None,
    "install_dir": None,
    "artifact_name": "package.zip",
}


class BuildType(enum.Enum):
    IN_CONTAINER_MERGED = enum.auto()
    IN_CONTAINER_SEPARATED = enum.auto()
    MERGED = enum.auto()
    SEPARATED = enum.auto()

    @classmethod
    def get_type(cls, options: dict):
        layer = get_path(options, "layer.artifact_name")
        handler = get_path(options, "handler.artifact_name")
        container_img = get_path(options, "docker.image")
        if container_img:
            if layer and handler:
                return cls.IN_CONTAINER_SEPARATED
            else:
                return cls.IN_CONTAINER_MERGED
        else:
            if layer and handler:
                return cls.SEPARATED
            else:
                return cls.MERGED


class BuildLambdaCommand(EnvCommand):
    name = "build-lambda"
    description = "Execute to build lambda lambda artifacts"

    arguments = [
        argument(
            "override",
            "Argument to override any configuration parameter."
            ' Ex. override="docker_dns=127.0.0.1"',
            multiple=False,
            optional=True,
        ),
    ]

    def _get_options(self) -> Any:
        options = defaultdict(dict)
        options.update(DEFAULT_OPTIONS)
        override_options = defaultdict(dict)

        pyproject_data = self.poetry.pyproject.data
        override = self.argument("override")

        if override.startswith("override="):
            override = override.removeprefix("override=")

        if override:
            for param in override.split(";"):
                try:
                    key, value = param.split("=", 1)
                    prefix, name = key.split("_", 1)
                    override_options[prefix][name] = value
                except ValueError:
                    raise Exception(
                        f"override argument has wrong value: {override}")

        pyproject_data = self.poetry.pyproject.data
        prefixes = ["layer", "handler", "docker", "artifacts"]

        plugin_conf = get_path(
            pyproject_data, "tool.poetry-plugin-lambda-build")
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
            create_separated_handler_package(self, options)
            create_separate_layer_package(self, options)
        elif _type == BuildType.SEPARATED:
            self.line("Building separated packages on local...", style="info")
            create_separate_layer_package(self, options, in_container=False)
            create_separated_handler_package(self, options, in_container=False)
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
