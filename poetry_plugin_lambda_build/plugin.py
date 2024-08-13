from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from cleo.helpers import argument, option
from cleo.io.inputs.argv_input import ArgvInput
from poetry.console.commands.command import Command
from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_plugin_lambda_build.parameters import ParametersContainer
from poetry_plugin_lambda_build.recipes import Builder

if TYPE_CHECKING:
    from poetry.console.application import Application


class BuildLambdaCommand(Command):  # noqa: D101
    name = "build-lambda"
    description = "Execute to build lambda artifacts"

    arguments = [  # noqa: RUF012
        argument(name, *params[:-1])
        for name, params in ParametersContainer.ARGS.items()
    ]
    options = [  # noqa: RUF012
        option(k, None, *params[:-1]) for k, params in ParametersContainer.OPTS.items()
    ]

    def _get_parameters(self) -> ParametersContainer:
        pyproject_data = self.poetry.pyproject.data
        self.container = ParametersContainer()

        try:
            plugin_conf = pyproject_data["tool"]["poetry-plugin-lambda-build"]
        except KeyError:
            plugin_conf = None

        if plugin_conf:
            for k in plugin_conf:
                self.container.put(k, plugin_conf[k])

        input_ = self.io.input
        if not isinstance(input_, ArgvInput):
            msg = f"Unexpected input: {input_!r}"
            raise TypeError(msg)

        self.container.parse_tokens(input_._tokens[1:])  # noqa: SLF001

        return self.container

    def handle(self) -> Any:  # noqa: ANN401, D102
        parameters: ParametersContainer = self._get_parameters()
        Builder(self, parameters).build()
        self.line("\n✨ Done!")

    def info(self, txt: str):  # noqa: ANN201, D102
        return self.line(txt, style="info")

    def debug(self, txt: str):  # noqa: ANN201, D102
        return self.line(txt, style="debug")

    def error(self, txt: str):  # noqa: ANN201, D102
        return self.line(txt, style="error")

    def warning(self, txt: str):  # noqa: ANN201, D102
        return self.line(txt, style="warning")


def factory() -> BuildLambdaCommand:  # noqa: D103
    return BuildLambdaCommand()


class LambdaPlugin(ApplicationPlugin):  # noqa: D101
    def activate(self, application: Application, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401, ARG002, D102
        application.command_loader.register_factory("build-lambda", factory)
