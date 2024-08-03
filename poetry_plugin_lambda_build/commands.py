from poetry_plugin_lambda_build.utils import join_cmds

MKDIR = "mkdir -p {output_dir}".split(" ")
INSTALL_DEPS_CMD_TMPL = (
    "pip install -q -t {output_dir} --no-cache-dir -r {requirements}".split(" ")
)
INSTALL_POETRY_CMD = "pip install poetry --quiet --upgrade pip".split(" ")
INSTALL_CMD_TMPL = "poetry run pip install -q -t {output_dir} . --no-cache-dir --upgrade {indexes}".split(
    " "
)
INSTALL_NO_DEPS_CMD_TMPL = "poetry run pip install -q -t {output_dir} . --no-cache-dir --no-deps --upgrade".split(
    " "
)

INSTALL_DEPS_CMD_IN_CONTAINER_TMPL = join_cmds(MKDIR, INSTALL_DEPS_CMD_TMPL)

INSTALL_IN_CONTAINER_CMD_TMPL = join_cmds(MKDIR, INSTALL_POETRY_CMD, INSTALL_CMD_TMPL)

INSTALL_IN_CONTAINER_NO_DEPS_CMD_TMPL = join_cmds(
    MKDIR, INSTALL_POETRY_CMD, INSTALL_NO_DEPS_CMD_TMPL
)
