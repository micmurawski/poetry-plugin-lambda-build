from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from typing import Generator

from poetry.console.commands.command import Command


def join_cmds(*cmds: list[str], joiner: str = " && ") -> str:
    return joiner.join(cmds)


@contextmanager
def cd(path) -> Generator[None, None, None]:
    old_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)


def remove_prefix(text: str, prefix: str) -> str:
    return text[len(prefix):] if text.startswith(prefix) and prefix else text


def remove_suffix(text: str, suffix: str) -> str:
    return text[:-len(suffix)] if text.endswith(suffix) and suffix else text


def mask_string(s: str) -> str:
    return f'{s[:14]}{"*" * len(s)}'


def run_python_cmd(*args: list[str],
                   cmd: Command | None = None,
                   **kwargs) -> int:
    cmd = [sys.executable, *args]
    return run_cmd(*cmd, **kwargs)


def run_cmd(
    *args: list[str],
    cmd: Command | None = None,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs
) -> int:
    cmd = args
    process = subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        **kwargs
    )
    if cmd is None:
        while process.poll() is None:
            cmd.line(process.stdout.readline().decode()[:-1], style="info")
    else:
        while process.poll() is None:
            print(process.stdout.readline().decode(), end="")

    _, error = process.communicate()

    if process.returncode != 0:
        sys.stderr.write(error.decode())
        raise RuntimeError(
            f"Error occurred while running {' '.join(cmd)}", error.decode(
            ), process.returncode
        )

    return process.returncode


def format_str(string: str, **kwargs) -> str:
    for k, v in kwargs.items():
        pattern = "{"+k+"}"
        if pattern in string:
            string = string.replace(pattern, v)
    if "{" in string or "}" in string:
        raise Exception("Missed params", string, kwargs)
    return string
