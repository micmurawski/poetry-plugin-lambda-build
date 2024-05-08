from __future__ import annotations

from typing import Any

from poetry.console.exceptions import PoetryConsoleError

from poetry_plugin_lambda_build.utils import remove_prefix

DEFAULT_PARAMETERS = {
    "docker_entrypoint": "/bin/bash",
    "docker_network": "host",
    "package_artifact_path": "package.zip",
    "without": [],
    "only": [],
    "with": [],
}


def comma_separated_collection(x): return x.split(",")


ARGS = {
    "docker_image": ("The image to run", True, False, None, str),
    "docker_entrypoint": ("The entrypoint for the container (comma separated string)", True, False, None, str),
    "docker_environment": ("Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2", True, False, None, str),
    "docker_dns": ("Set custom DNS servers (comma separated string)", True, False, None, str),
    "docker_network": ("The name of the network this container will be connected to at creation time", True, False, None, str),
    "docker_network_disabled": ("Disable networking ex. docker_network_disabled=0", True, False, None, str),
    "docker_network_mode": ("Network_mode", True, False, None),
    "docker_platform": ("Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.", True, False, None, str),
    "package_install_dir": ("Installation directory inside zip artifact for single zip package", True, False, None, str),
    "layer_install_dir": ("Installation directory inside zip artifact for layer zip package", True, False, None, str),
    "function_install_dir": ("Installation directory inside zip artifact for function zip package", True, False, None, str),
    "install_dir": ("Installation directory inside zip artifact for zip package (not function layer separation)", True, False, None, str),
    "package_artifact_path": ("Output package path", True, False, None, str),
    "layer_artifact_path": ("Output layer package path", True, False, None, str),
    "function_artifact_path": ("Output function package path", True, False, None, str),
    "only": ("The only dependency groups to include", True, False, None, comma_separated_collection),
    "without": ("The dependency groups to ignore", True, False, None, comma_separated_collection),
    "with": ("The optional dependency groups to include", True, False, None, comma_separated_collection),
    "zip_compresslevel": ("None (default for the given compression type) or an integer "
                          "specifying the level to pass to the compressor. "
                          "When using ZIP_STORED or ZIP_LZMA this keyword has no effect. "
                          "When using ZIP_DEFLATED integers 0 through 9 are accepted. "
                          "When using ZIP_BZIP2 integers 1 through 9 are accepted.", True, False, None, int),
    "zip_compression": ("ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib), ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma)", True, False, None, str),
}


class ParametersContainer(dict):
    ARGS = ARGS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update(DEFAULT_PARAMETERS)

    def put(self, key: Any, value: Any) -> None:
        _parser = self.ARGS[key][-1]
        self[key] = _parser(value)

    def __getitem__(self, key: Any) -> Any:
        if key not in self.ARGS:
            raise PoetryConsoleError(
                f"<error>Error: Bad input parameter: {key} run poetry build-lambda --help for more info</error>")
        return super().__getitem__(key)

    def get_section(self, section: str) -> dict:
        return {remove_prefix(k, section+"_"): self[k] for k in self if k.startswith(section)}

    @property
    def groups(self) -> dict:
        _keys = {"with", "without", "only"}
        return {k: set(self[k]) if self[k] else set() for k in _keys}
