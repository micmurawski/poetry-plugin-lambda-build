from __future__ import annotations

from typing import Any

from cleo.application import Application
from cleo.helpers import argument
from poetry.console.commands.env_command import EnvCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_plugin_lambda_build.parameters import ParametersContainer
from poetry_plugin_lambda_build.recipes import Builder


class BuildLambdaCommand(EnvCommand):
    name = "build-lambda"
    description = "Execute to build lambda lambda artifacts"

    arguments = [
        argument(name, *params[:-1]) for name, params in ParametersContainer.ARGS.items()
    ]

    def _get_parameters(self) -> ParametersContainer:
        pyproject_data = self.poetry.pyproject.data
        container = ParametersContainer()
        for token in filter(lambda token: any([token.startswith(f"{arg}=") for arg in ParametersContainer.ARGS]), self.io.input._tokens[1:]):
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
        Builder(self, parameters).build()
        self.line("\n✨ Done!")

    def info(self, txt: str):
        return self.line(txt, style="info")

    def debug(self, txt: str):
        return self.line(txt, style="debug")

    def error(self, txt: str):
        return self.line(txt, style="error")

    def warning(self, txt: str):
        return self.line(txt, style="warning")


def factory() -> BuildLambdaCommand:
    return BuildLambdaCommand()


class LambdaPlugin(ApplicationPlugin):
    def activate(self, application: Application, *args: Any, **kwargs: Any) -> None:
        application.command_loader.register_factory("build-lambda", factory)
