# Poetry Plugin Lambda Build

The plugin for poetry that allows you to build zip packages suited for serverless deployment like AWS Lambda, Google App Engine, Azure App Service, and more...

Additionally it provides docker container support for build inside container


## Installation

poetry self add poetry-plugin-lambda-build


## Configuration Examples
### AWS Lambda - all in one - dependencies and handler in the same zip package - Default

```.toml
[tool.poetry-plugin-lambda-build]
artifact_name = "package.zip"
```

### AWS Lambda - all in one - layer package
```
[tool.poetry-plugin-lambda-build]
install_dir = "lambda/python"
artifact_name = "layer.zip"
```
### AWS Lambda - separated - separate layer package and handler package

```
[tool.poetry-plugin-lambda-build]
layer_artifact_name = "layer.zip"
layer_install_dir = "lambda/python"
handler_artifact_name = "handler.zip"
```
### AWS Lambda - separated - separate layer package and handler package build in docker container

```
[tool.poetry-plugin-lambda-build]
docker_image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker_network = "host"
layer_artifact_name = "layer.zip"
layer_install_dir = "lambda/python"
handler_artifact_name = "handler.zip"
```


