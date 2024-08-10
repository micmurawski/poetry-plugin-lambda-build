from __future__ import annotations

import shlex
from typing import Any

from poetry.console.exceptions import PoetryConsoleError

from poetry_plugin_lambda_build.utils import remove_prefix


def comma_separated_collection(x: str) -> list[str]:
    return x.split(",")


ARGS = {
    "docker-image": ("The image to run", True, False, None, str),
    "docker-entrypoint": (
        "The entrypoint for the container (comma separated string)",
        True,
        False,
        "/bin/bash",
        str,
    ),
    "docker-environment": (
        "Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2",
        True,
        False,
        None,
        str,
    ),
    "docker-dns": (
        "Set custom DNS servers (comma separated string)",
        True,
        False,
        None,
        str,
    ),
    "docker-network": (
        "The name of the network this container will be connected to at creation time",
        True,
        False,
        "host",
        str,
    ),
    "docker-network-mode": ("Network-mode", True, False, None, str),
    "docker-platform": (
        "Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.",
        True,
        False,
        None,
        str,
    ),
    "package-artifact-path": (
        "Output package path (default: package.zip). Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.",
        True,
        False,
        "package.zip",
        str,
    ),
    "package-install-dir": (
        "Installation directory inside artifact for single package",
        True,
        False,
        "",
        str,
    ),
    "function-artifact-path": (
        "Output function package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.",
        True,
        False,
        None,
        str,
    ),
    "function-install-dir": (
        "Installation directory inside artifact for function package",
        True,
        False,
        "",
        str,
    ),
    "layer-artifact-path": (
        "Output layer package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.",
        True,
        False,
        None,
        str,
    ),
    "layer-install-dir": (
        "Installation directory inside artifact for layer package",
        True,
        False,
        "",
        str,
    ),
    "only": (
        "The only dependency groups to include",
        True,
        False,
        [],
        comma_separated_collection,
    ),
    "without": (
        "The dependency groups to ignore",
        True,
        False,
        [],
        comma_separated_collection,
    ),
    "with": (
        "The optional dependency groups to include",
        True,
        False,
        [],
        comma_separated_collection,
    ),
    "zip-compresslevel": (
        "None (default for the given compression type) or an integer "
        "specifying the level to pass to the compressor. "
        "When using ZIP_STORED or ZIP_LZMA this keyword has no effect. "
        "When using ZIP_DEFLATED integers 0 through 9 are accepted. "
        "When using ZIP_BZIP2 integers 1 through 9 are accepted.",
        True,
        False,
        None,
        int,
    ),
    "zip-compression": (
        "ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib), ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma)",
        True,
        False,
        "ZIP_STORED",
        str,
    ),
    "pre-install-script": (
        "The script that is executed before installation.",
        True,
        False,
        None,
        shlex.split,
    ),
}


OPTS = {
    "no-checksum": ("Enable to suppress checksum checking", True, False, False, bool),
    "docker-network-disabled": ("Disable networking", True, False, None, bool),
}


class ParametersContainer(dict):
    ARGS = ARGS
    OPTS = OPTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.ARGS.items():
            self[k] = v[-2]

        for k, v in self.OPTS.items():
            self[k] = v[-2]

    def put(self, key: Any, value: Any) -> None:
        if value is not None:
            self.check_key(key, raise_error=True)
            _parser = (self.ARGS.get(key) or self.OPTS[key])[-1]
            self[key] = _parser(value)

    def is_in_opts(self, key: str) -> bool:
        return key in self.OPTS

    def is_in_args(self, key: str) -> bool:
        return key in self.ARGS

    def check_key(self, key: Any, raise_error: bool = False) -> bool:
        is_in = self.is_in_args(key) or self.is_in_opts(key)
        if (not is_in) and raise_error:
            raise PoetryConsoleError(
                f"<error>Error: Bad input parameter: {key} run poetry build-lambda --help for more info</error>"
            )
        return is_in

    def __getitem__(self, key: Any) -> Any:
        self.check_key(key)
        return super().__getitem__(key)

    def get_section(self, section: str) -> dict:
        return {
            remove_prefix(k, section + "-").replace("-", "_"): self[k]
            for k in self
            if k.startswith(section)
        }

    @property
    def groups(self) -> dict:
        _keys = {"with", "without", "only"}
        return {k: set(self[k]) if self[k] else set() for k in _keys}

    def _iter_tokens(self, tokens):
        i = 0
        while i < len(tokens):
            token = tokens[i].strip()

            if token.startswith("--"):
                if self.is_in_opts(token[2:]):
                    yield token[2:], True

            elif tokens[i].startswith("-") or len(tokens[i]) == 0:
                pass
            elif "=" in token:
                k, v = token.split("=")
                yield k, v
            else:
                val = str(next(self._iter_tokens(tokens[i + 1 :]), ""))
                yield token, val
                i += 1
            i += 1

    def parse_tokens(self, tokens: list[str]):
        for k, v in self._iter_tokens(tokens):
            self.put(k, v)
