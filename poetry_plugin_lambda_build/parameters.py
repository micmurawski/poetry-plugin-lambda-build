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


def comma_separated_collection(x: str) -> list[str]: return x.split(",")


def str2bool(
    x: str) -> bool: return False if x.lower() in {"0", "false"} else True


ARGS = {
    "docker_image": ("The image to run", True, False, None, str),
    "docker_entrypoint": ("The entrypoint for the container (comma separated string)", True, False, None, str),
    "docker_environment": ("Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2", True, False, None, str),
    "docker_dns": ("Set custom DNS servers (comma separated string)", True, False, None, str),
    "docker_network": ("The name of the network this container will be connected to at creation time", True, False, None, str),
    "docker_network_disabled": ("Disable networking ex. docker_network_disabled=0", True, False, None, str),
    "docker_network_mode": ("Network_mode", True, False, None),
    "docker_platform": ("Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.", True, False, None, str),
    "package_artifact_path": ("Output package path (default: package.zip). Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.", True, False, None, str),
    "package_install_dir": ("Installation directory inside artifact for single package", True, False, None, str),
    "function_artifact_path": ("Output function package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.", True, False, None, str),
    "function_install_dir": ("Installation directory inside artifact for function package", True, False, None, str),
    "layer_artifact_path": ("Output layer package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.", True, False, None, str),
    "layer_install_dir": ("Installation directory inside artifact for layer package", True, False, None, str),
    "only": ("The only dependency groups to include", True, False, None, comma_separated_collection),
    "without": ("The dependency groups to ignore", True, False, None, comma_separated_collection),
    "with": ("The optional dependency groups to include", True, False, None, comma_separated_collection),
    "zip_compresslevel": ("None (default for the given compression type) or an integer "
                          "specifying the level to pass to the compressor. "
                          "When using ZIP_STORED or ZIP_LZMA this keyword has no effect. "
                          "When using ZIP_DEFLATED integers 0 through 9 are accepted. "
                          "When using ZIP_BZIP2 integers 1 through 9 are accepted.", True, False, None, int),
    "zip_compression": ("ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib), ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma)", True, False, None, str),
    "pre_install_script": ("The script that is executed before installation.", True, False, None, str),
    "suppress_checksum": ("Enable to suppress checksum checking", True, False, False, str2bool),
}


class ParametersContainer(dict):
    ARGS = ARGS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in ARGS.items():
            self[k] = v[-2]
        self.update(DEFAULT_PARAMETERS)

    def put(self, key: Any, value: Any) -> None:
        if value:
            self.check_key(key)
            _parser = self.ARGS[key][-1]
            self[key] = _parser(value)

    def check_key(self, key: Any) -> bool:
        if key not in self.ARGS:
            raise PoetryConsoleError(
                f"<error>Error: Bad input parameter: {key} run poetry build-lambda --help for more info</error>")

    def __getitem__(self, key: Any) -> Any:
        self.check_key(key)
        return super().__getitem__(key)

    def get_section(self, section: str) -> dict:
        return {remove_prefix(k, section+"_"): self[k] for k in self if k.startswith(section)}

    @property
    def groups(self) -> dict:
        _keys = {"with", "without", "only"}
        return {k: set(self[k]) if self[k] else set() for k in _keys}
