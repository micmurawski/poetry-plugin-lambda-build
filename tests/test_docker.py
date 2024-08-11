from docker.models.containers import Container


def test_docker():
    from poetry_plugin_lambda_build.docker import get_docker_client
    client = get_docker_client()
    image = "public.ecr.aws/sam/build-python3.12:latest-x86_64"
    docker_container: Container = get_docker_client().containers.run(
        "ubuntu", "echo hello world",
        image, tty=True, detach=True
    )
    assert docker_container
    docker_container.kill()
    docker_container.remove(v=True)