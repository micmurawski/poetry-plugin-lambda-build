from __future__ import annotations

import os
import tarfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Generator

import docker
from docker.models.containers import Container

from poetry_plugin_lambda_build.utils import cd


def _parse_str_to_bool(value: str) -> bool:
    if value.lower() in ("0", "false"):
        return False
    return True


def _parse_str_to_list(value: str) -> list[str]:
    return value.split(",")


ARGS_PARSERS = {
    "environment": _parse_str_to_list,
    "dns": _parse_str_to_list,
    "entrypoint": _parse_str_to_list,
    "docker_network_disabled": _parse_str_to_bool
}


def get_docker_client() -> docker.DockerClient:
    return docker.from_env()


def copy_to(src: str, dst: str):
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


def copy_from(src: str, dst: str):
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
    options: dict = {k: True for k in kwargs.pop("options", [])}
    kwargs: dict = {k: v for k, v in kwargs.items() if v}

    for arg in ARGS_PARSERS:
        if arg in kwargs:
            parser = ARGS_PARSERS[arg]
            kwargs[arg] = parser(kwargs[arg])

    docker_container: Container = get_docker_client().containers.run(
        image, **kwargs, **options, tty=True, detach=True
    )
    logger.debug(f"Running docker container image: {image}")
    try:
        yield docker_container
    finally:
        logger.debug("Killing docker container...")
        docker_container.kill()
        logger.debug("Removing docker container...")
        docker_container.remove(v=True)


def exec_run_container(logger, container: Container, entrypoint: str, container_cmd: str):
    _, stream = container.exec_run(
        f'{entrypoint} -c "{container_cmd}"',
        stdout=True,
        stderr=True,
        stream=True
    )
    for line in stream:
        logger.info(line.strip().decode())
