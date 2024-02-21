# Poetry Plugin Lambda Build

The plugin for poetry that allows you to build zip packages suited for serverless deployment like AWS Lambda, Google App Engine, Azure App Service, and more...

Additionally it provides docker container support for build inside container


## Installation

```bash
poetry self add poetry-plugin-lambda-build
poetry self add poetry-plugin-export
```

## Execution

Configure `pyproject.toml` with the following configuration. This is example for [AWS Lambda configuration](#aws)

```.toml
[tool.poetry-plugin-lambda-build]
docker_image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker_network = "host"
layer_artifact_name = "artifacts/layer.zip"
layer_install_dir = "python"
handler_artifact_name = "artifacts/handler.zip"
```

Running ...

```bash
poetry build-lambda
```
will build handler and layer packages for AWS Lambda deployment inside `public.ecr.aws/sam/build-python3.11:latest-x86_64` container.

```
artifacts
├── handler.zip
└── layer.zip
```

## Configuration Examples
### AWS Lambda - all in one - dependencies and handler in the same zip package - Default

```.toml
[tool.poetry-plugin-lambda-build]
artifact_name = "package.zip"
```

### AWS Lambda - all in one - layer package
```.toml
[tool.poetry-plugin-lambda-build]
install_dir = "python"
artifact_name = "layer.zip"
```
### AWS Lambda - separated - separate layer package and handler package

```.toml
[tool.poetry-plugin-lambda-build]
layer_artifact_name = "layer.zip"
layer_install_dir = "python"
handler_artifact_name = "handler.zip"
```
### <a name="aws"></a>AWS Lambda - separated - separate layer package and handler package build in docker container

```.toml
[tool.poetry-plugin-lambda-build]
docker_image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker_network = "host"
layer_artifact_name = "layer.zip"
layer_install_dir = "python"
handler_artifact_name = "handler.zip"
```


## Tips
#### Mac users with Docker Desktops
Make sure to configure `DOCKER_HOST` properly
```bash
export DOCKER_HOST=unix:///Users/$USER/.docker/run/docker.sock
```