from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from logging import Logger
from typing import Generator


def parse_poetry_args(tokens: list[str]) -> Generator[tuple[str], None, None]:
    i = 0
    while i < len(tokens):
        if "=" in tokens[i]:
            k, v = tokens[i].strip().split("=")
            yield k, v
        elif tokens[i].startswith("-") or len(tokens[i]) == 0:
            pass
        else:
            if i+1 < len(tokens):
                val = tokens[i+1].strip()
            else:
                val = None
            yield tokens[i].strip(), val
            i += 1
        i += 1


def join_cmds(*cmds: list[str], joiner: str = " && ") -> str:
    return joiner.join(cmds)


@contextmanager
def cd(path):
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


def run_python_cmd(
    *args: list[str],
    logger: Logger | None = None,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs
) -> int:
    return run_cmd(sys.executable, *args, logger=logger, stdout=stdout, stderr=stderr, **kwargs)


def run_cmd(
    *args: list[str],
    logger: Logger | None = None,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs
) -> int:
    cmd = []
    for a in args:
        cmd += a.split(" ")
    process = subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        **kwargs
    )
    if logger:
        while process.poll() is None:
            logger.info(process.stdout.readline().decode())
    else:
        while process.poll() is None:
            sys.stdout.write(process.stdout.readline().decode())

    _, error = process.communicate()

    if process.returncode != 0:
        if logger:
            logger.error(error.decode())
        else:
            sys.stderr.write(error.decode())
        raise RuntimeError(
            error.decode(),
            process.returncode,
        )

    return process.returncode


def format_str(string: str, **kwargs) -> str:
    for k, v in kwargs.items():
        pattern = "{"+k+"}"
        if pattern in string:
            string = string.replace(pattern, v)
    return string
