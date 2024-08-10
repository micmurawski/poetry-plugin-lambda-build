from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from contextlib import contextmanager
from fnmatch import fnmatch
from functools import reduce
from logging import Logger
from operator import or_
from pathlib import Path
from typing import Generator


def join_cmds(*cmds: list[list[str]], joiner: str = "&&") -> list[str]:
    _cmds = list(filter(lambda x: x, cmds))
    result = []
    for i, cmd in enumerate(_cmds):
        result += cmd
        if i < len(_cmds) - 1:
            result.append(joiner)
    return result


def cmd_split(cmd: list[str], separator="&&") -> Generator[None, None, list[str]]:
    result = []
    for c in cmd:
        if c == separator:
            yield result
            result = []
        else:
            result.append(c)
    yield result


@contextmanager
def cd(path):
    old_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)


def remove_prefix(text: str, prefix: str) -> str:
    return text[len(prefix) :] if text.startswith(prefix) and prefix else text


def remove_suffix(text: str, suffix: str) -> str:
    return text[: -len(suffix)] if text.endswith(suffix) and suffix else text


def mask_string(s: str) -> str:
    return f'{s[:14]}{"*" * len(s)}'


def run_cmd(
    *cmd: list[str],
    logger: Logger | None = None,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs,
) -> int:
    process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, **kwargs)
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


def run_cmds(
    cmds: list[str],
    print_safe_cmds: list[str],
    logger: Logger,
    stdout: int = subprocess.PIPE,
    stderr: int = subprocess.PIPE,
    **kwargs,
) -> int:
    for cmd, print_safe_cmd in zip(cmd_split(cmds), cmd_split(print_safe_cmds)):
        logger.debug(f"Executing: {' '.join(print_safe_cmd)}")
        run_cmd(*cmd, logger=logger, stdout=stdout, stderr=stderr, **kwargs)


def format_cmd(cmd: list[str], **kwargs) -> list[str]:
    """
    Formats a command by joining its elements into a single string,
    replacing placeholders with provided keyword arguments, and then
    splitting the string back into a list of arguments.

    Args:
        cmd (list[str]): The command to format.
        **kwargs: Keyword arguments to replace placeholders in the command.

    Returns:
        list[str]: The formatted command as a list of arguments.
    """
    split_marker = "----"
    return (
        split_marker.join(cmd)
        .format(
            **dict(
                (k, split_marker.join(v)) if isinstance(v, list) else (k, v)
                for k, v in kwargs.items()
            )
        )
        .split(split_marker)
    )


def compute_checksum(path: str | Path, exclude: None | list[str | Path] = None) -> str:
    m = hashlib.md5()

    if exclude is None:
        exclude = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file_read in files:
                full_path = os.path.join(root, file_read)
                if not reduce(
                    or_, [fnmatch(full_path, pattern) for pattern in exclude], False
                ):
                    m.update(str(os.stat(full_path)).encode())
    else:
        m.update(str(os.stat(path)).encode())
    return m.hexdigest()
