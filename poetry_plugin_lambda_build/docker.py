from __future__ import annotations

import os
import tarfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Generator

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


def copy_to_container(src: str, dst: str):
    name, dst = dst.split(":")
    container = get_docker_client().containers.get(name)

    with TemporaryDirectory() as tmp_dir:
        src_name = os.path.basename(src)
        tar_filename = src_name + "_archive.tar"
        tar_path = os.path.join(tmp_dir, tar_filename)
        tar = tarfile.open(tar_path, mode="w")
        with cd(os.path.dirname(src)):
            try:
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
def run_container(logger, **kwargs) -> Generator[Container, None, None]:
    image: str = kwargs.pop("image")

    for k, v in kwargs.items():
        if k in ARGS_PARSERS and v:
            parser = ARGS_PARSERS[k]
            kwargs[k] = parser(v)

    docker_container: Container = get_docker_client().containers.run(
        image, **kwargs, tty=True, detach=True
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
    logger, container: Container, container_cmd: list[str], print_safe_cmds: list[str]
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
        )
        for line in stream:
            logger.info(line.strip().decode())

        if exit_code and exit_code != 0:
            raise RuntimeError(
                f"Exec run in container resulted with exit code: {exit_code}"
            )
