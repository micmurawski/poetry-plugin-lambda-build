from __future__ import annotations

import os
import tarfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Generator, List, Optional
import fnmatch

import docker
from docker.models.containers import Container

from poetry_plugin_lambda_build.utils import cd, cmd_split


def _parse_str_to_list(value: str) -> list[str]:
    return value.split(",")


ARGS_PARSERS = {
    "environment": _parse_str_to_list,
    "dns": _parse_str_to_list,
    "entrypoint": _parse_str_to_list,
    "network_disabled": bool,
}


def get_docker_client() -> docker.DockerClient:
    return docker.from_env()


def _should_ignore(path: str, ignore_patterns: Optional[List[str]] = None) -> bool:
    """Check if a path should be ignored based on the provided patterns."""
    if not ignore_patterns:
        return False
    return any(fnmatch.fnmatch(path, pattern) for pattern in ignore_patterns)


def _read_dockerignore_file(file_path: str) -> List[str]:
    """Read patterns from a .dockerignore file."""
    if not os.path.exists(file_path):
        return []
    
    patterns = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


def copy_to_container(src: str, dst: str, ignore_patterns: Optional[List[str]] = None, dockerignore_file: Optional[str] = None):
    name, dst = dst.split(":")
    container = get_docker_client().containers.get(name)
    container.exec_run(["mkdir", "-p", os.path.dirname(dst)])

    # Read patterns from dockerignore file if provided
    if dockerignore_file:
        ignore_patterns = ignore_patterns or []
        ignore_patterns.extend(_read_dockerignore_file(dockerignore_file))

    with TemporaryDirectory() as tmp_dir:
        src_name = os.path.basename(src)
        tar_filename = src_name + "_archive.tar"
        tar_path = os.path.join(tmp_dir, tar_filename)
        tar = tarfile.open(tar_path, mode="w")
        
        with cd(os.path.dirname(src)):
            try:
                # Check if the file should be ignored
                if not _should_ignore(src_name, ignore_patterns):
                    tar.add(src_name)
            finally:
                tar.close()

            data = open(tar_path, "rb").read()
            container.put_archive(os.path.dirname(dst), data)


def copy_from_container(src: str, dst: str):
    name, src = src.split(":")
    container = get_docker_client().containers.get(name)
    tar_path = dst + "_archive.tar"
    f = open(tar_path, "wb")
    bits, _ = container.get_archive(src)
    for chunk in bits:
        f.write(chunk)
    f.close()
    tar = tarfile.open(tar_path)
    tar.extractall(dst)
    tar.close()
    os.remove(tar_path)


@contextmanager
def run_container(logger, local_dependencies: list[str] | None = None, working_dir: str = "/", **kwargs) -> Generator[Container, None, None]:
    image: str = kwargs.pop("image")

    for k, v in kwargs.items():
        if k in ARGS_PARSERS and v:
            parser = ARGS_PARSERS[k]
            kwargs[k] = parser(v)

    # Handle local dependencies by adding volumes
    if local_dependencies:
        volumes = kwargs.get("volumes", {})
        for dep in local_dependencies:
            source = dep
            target = dep
            volumes[os.path.abspath(source)] = {"bind": target, "mode": "rw"}
        kwargs["volumes"] = volumes
    
    docker_container: Container = get_docker_client().containers.run(
        image, **kwargs, tty=True, detach=True, working_dir=working_dir
    )
    logger.debug(f"Running docker container image: {image}")
    try:
        yield docker_container
    finally:
        logger.debug("Killing docker container...")
        docker_container.kill()
        logger.debug("Removing docker container...")
        docker_container.remove(v=True)


def exec_run_container(
    logger, container: Container, container_cmd: list[str], print_safe_cmds: list[str], working_dir: str = "/"
):        
    for cmd, print_safe_cmd in zip(
        cmd_split(container_cmd), cmd_split(print_safe_cmds)
    ):
        logger.debug(f"Executing: {' '.join(print_safe_cmd)}")
        exit_code, stream = container.exec_run(
            cmd,
            stdout=True,
            stderr=True,
            stream=True,
            workdir=working_dir,
        )
        for line in stream:
            logger.info(line.strip().decode())

        if exit_code and exit_code != 0:
            raise RuntimeError(
                f"Exec run in container resulted with exit code: {exit_code}"
            )
