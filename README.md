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
docker-image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker-network = "host"
layer-artifact-path = "artifacts/layer.zip"
layer-install-dir = "python"
function-artifact-path = "artifacts/function.zip"
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

Running ...

```bash
poetry build-lambda docker-image="public.ecr.aws/sam/build-python3.12:latest-x86_64"
```

will override `docker-image` value in config 

## Configuration Examples
### AWS Lambda - all in one - dependencies and function in the same zip package - Default

```.toml
[tool.poetry-plugin-lambda-build]
package-artifact-path = "package.zip"
```

### AWS Lambda - all in one - layer package
```.toml
[tool.poetry-plugin-lambda-build]
package-install-dir = "python"
package-artifact-path = "layer.zip"
```
### AWS Lambda - separated - separate layer package and function package

```.toml
[tool.poetry-plugin-lambda-build]
layer-artifact-path = "layer.zip"
layer-install-dir = "python"
function-artifact-path = "function.zip"
```
### <a name="aws"></a>AWS Lambda - separated - separate layer package and function package build in docker container

```.toml
[tool.poetry-plugin-lambda-build]
docker-image = "public.ecr.aws/sam/build-python3.11:latest-x86_64"
docker-network = "host"
layer-artifact-path = "layer.zip"
layer-install-dir = "python"
function-artifact-path = "function.zip"
```

## Help

```bash
poetry build-lambda help
```

```
Description:
  Execute to build lambda lambda artifacts

Usage:
  build-lambda [options] [--] [<docker-image> [<docker-entrypoint> [<docker-environment> [<docker-dns> [<docker-network> [<docker-network-mode> [<docker-platform> [<package-artifact-path> [<package-install-dir> [<function-artifact-path> [<function-install-dir> [<layer-artifact-path> [<layer-install-dir> [<only> [<without> [<with> [<zip-compresslevel> [<zip-compression> [<pre-install-script>]]]]]]]]]]]]]]]]]]]

Arguments:
  docker-image               The image to run
  docker-entrypoint          The entrypoint for the container (comma separated string) [default: "/bin/bash"]
  docker-environment         Environment variables to set inside the container (comma separated string) ex. VAR_1=VALUE_1,VAR_2=VALUE_2
  docker-dns                 Set custom DNS servers (comma separated string)
  docker-network             The name of the network this container will be connected to at creation time [default: "host"]
  docker-network-mode        Network-mode
  docker-platform            Platform in the format os[/arch[/variant]]. Only used if the method needs to pull the requested image.
  package-artifact-path      Output package path (default: package.zip). Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory. [default: "package.zip"]
  package-install-dir        Installation directory inside artifact for single package [default: ""]
  function-artifact-path     Output function package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.
  function-install-dir       Installation directory inside artifact for function package [default: ""]
  layer-artifact-path        Output layer package path. Set the '.zip' extension to wrap the artifact into a zip package otherwise, output will be created in the directory.
  layer-install-dir          Installation directory inside artifact for layer package [default: ""]
  only                       The only dependency groups to include
  without                    The dependency groups to ignore
  with                       The optional dependency groups to include
  zip-compresslevel          None (default for the given compression type) or an integer specifying the level to pass to the compressor. When using ZIP_STORED or ZIP_LZMA this keyword has no effect. When using ZIP_DEFLATED integers 0 through 9 are accepted. When using ZIP_BZIP2 integers 1 through 9 are accepted.
  zip-compression            ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib), ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma) [default: "ZIP_STORED"]
  pre-install-script         The script that is executed before installation.

Options:
      --no-checksum              Enable to suppress checksum checking
      --docker-network-disabled  Disable networking
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