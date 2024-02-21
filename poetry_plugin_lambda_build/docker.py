import os
import tarfile
from contextlib import contextmanager
from functools import cache

import docker
from poetry.console.commands.env_command import EnvCommand


@cache
def get_docker_client() -> docker.DockerClient:
    return docker.from_env()


def copy_to(src: str, dst: str):
    name, dst = dst.split(":")
    container = get_docker_client().containers.get(name)

    os.chdir(os.path.dirname(src))
    src_name = os.path.basename(src)
    tar = tarfile.open(src + ".tar", mode="w")
    try:
        tar.add(src_name)
    finally:
        tar.close()

    data = open(src + ".tar", "rb").read()
    container.put_archive(os.path.dirname(dst), data)


def copy_from(src: str, dst: str):
    name, src = src.split(":")
    container = get_docker_client().containers.get(name)
    tar_path = dst + ".tar"
    f = open(tar_path, "wb")
    bits, _ = container.get_archive(src)
    for chunk in bits:
        f.write(chunk)
    f.close()
    tar = tarfile.open(tar_path)
    tar.extractall(dst)
    os.remove(tar_path)


@contextmanager
def run_container(env_cmd: EnvCommand, *args, **kwargs):
    image: str = kwargs.pop("image")
    options: dict = {k: True for k in kwargs.pop("options", [])}
    kwargs: dict = {k: v for k, v in kwargs.items() if v}

    if "dns" in kwargs:
        kwargs["dns"] = kwargs["dns"].split(",")

    if "environment" in kwargs:
        kwargs["environment"] = kwargs["environment"].split(",")

    docker_container = get_docker_client().containers.run(
        image, **kwargs, **options, tty=True, detach=True
    )
    env_cmd.line(f"Running docker container image: {image}", style="debug")
    try:
        yield docker_container
    finally:
        env_cmd.line("Killing docker container...", style="debug")
        docker_container.kill()
        env_cmd.line("Removing docker container...", style="debug")
        docker_container.remove(v=True)
