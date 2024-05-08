# Poetry Plugin Lambda Build

The plugin for poetry that allows you to build zip packages suited for serverless deployment like AWS Lambda, Google App Engine, Azure App Service, and more...

Additionally it provides docker container support for build inside container

[![Test](https://github.com/micmurawski/poetry-plugin-lambda-build/actions/workflows/test.yml/badge.svg)](https://github.com/micmurawski/poetry-plugin-lambda-build/actions/workflows/test.yml)

## Installation

```bash
poetry self add poetry-plugin-lambda-build
```

## Execution

Configure `pyproject.toml` with the following configuration. This is example for [AWS Lambda configuration](#aws)

```.toml
[tool.poetry-plugin-lambda-build]
docker_image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker_network = "host"
layer_artifact_path = "artifacts/layer.zip"
layer_install_dir = "python"
function_artifact_path = "artifacts/function.zip"
```

Running ...

```bash
poetry build-lambda
```
will build function and layer packages for AWS Lambda deployment inside `public.ecr.aws/sam/build-python3.11:latest-x86_64` container.

```
artifacts
├── function.zip
└── layer.zip
```

## Configuration Examples
### AWS Lambda - all in one - dependencies and function in the same zip package - Default

```.toml
[tool.poetry-plugin-lambda-build]
artifact_path = "package.zip"
```

### AWS Lambda - all in one - layer package
```.toml
[tool.poetry-plugin-lambda-build]
install_dir = "python"
artifact_path = "layer.zip"
```
### AWS Lambda - separated - separate layer package and function package

```.toml
[tool.poetry-plugin-lambda-build]
layer_artifact_path = "layer.zip"
layer_install_dir = "python"
function_artifact_path = "function.zip"
```
### <a name="aws"></a>AWS Lambda - separated - separate layer package and function package build in docker container

```.toml
[tool.poetry-plugin-lambda-build]
docker_image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker_network = "host"
layer_artifact_path = "layer.zip"
layer_install_dir = "python"
function_artifact_path = "function.zip"
```

## Help

```bash
poetry build-lambda help
```

```
Description:
  Execute to build lambda lambda artifacts

Usage:
  build-lambda [options] [--] [<docker_image> [<docker_entrypoint> [<docker_environment> [<docker_dns> [<docker_network> [<docker_network_disabled> [<docker_network_mode> [<docker_platform> [<package_install_dir> [<layer_install_dir> [<function_install_dir> [<install_dir> [<package_artifact_path> [<layer_artifact_path> [<function_artifact_path> [<only> [<without> [<with> [<zip_compresslevel> [<zip_compression>]]]]]]]]]]]]]]]]]]]]

Arguments:
  docker_image               The image to run
  docker_entrypoint          The entrypoint for the container (comma separated string)
  docker_environment         Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2
  docker_dns                 Set custom DNS servers (comma separated string)
  docker_network             The name of the network this container will be connected to at creation time
  docker_network_disabled    Disable networking ex. docker_network_disabled=0
  docker_network_mode        Network_mode
  docker_platform            Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.
  package_install_dir        Installation directory inside zip artifact for single zip package
  layer_install_dir          Installation directory inside zip artifact for layer zip package
  function_install_dir       Installation directory inside zip artifact for function zip package
  install_dir                Installation directory inside zip artifact for zip package (not function layer separation)
  package_artifact_path      Output package path
  layer_artifact_path        Output layer package path
  function_artifact_path     Output function package path
  only                       The only dependency groups to include
  without                    The dependency groups to ignore
  with                       The optional dependency groups to include
  zip_compresslevel          None (default for the given compression type) or an integer specifying the level to pass to the compressor. When using ZIP_STORED or ZIP_LZMA this keyword has no effect. When using ZIP_DEFLATED integers 0 through 9 are accepted. When using ZIP_BZIP2 integers 1 through 9 are accepted.
  zip_compression            ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib), ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma)

Options:
  -h, --help                 Display help for the given command. When no command is given display help for the list command.
  -q, --quiet                Do not output any message.
  -V, --version              Display this application version.
      --ansi                 Force ANSI output.
      --no-ansi              Disable ANSI output.
  -n, --no-interaction       Do not ask any interactive question.
      --no-plugins           Disables plugins.
      --no-cache             Disables Poetry source caches.
  -C, --directory=DIRECTORY  The working directory for the Poetry command (defaults to the current working directory).
  -v|vv|vvv, --verbose       Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.
```

## Tips
#### Mac users with Docker Desktops
Make sure to configure `DOCKER_HOST` properly
```bash
export DOCKER_HOST=unix:///Users/$USER/.docker/run/docker.sock
```