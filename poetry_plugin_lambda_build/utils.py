from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager

from logging import Logger
from pathlib import Path
import hashlib
from fnmatch import fnmatch
from functools import reduce
from operator import or_


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


def compute_checksum(path: str | Path, exclude: None | list[str | Path] = None) -> str:
    m = hashlib.md5()

    if exclude is None:
        exclude = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file_read in files:
                full_path = os.path.join(root, file_read)
                if not reduce(
                    or_, [fnmatch(full_path, pattern)
                          for pattern in exclude], False
                ):
                    m.update(str(os.stat(full_path)).encode())
    else:
        m.update(str(os.stat(path)).encode())
    return m.hexdigest()
