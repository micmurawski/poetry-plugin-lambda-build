from poetry_plugin_lambda_build.utils import join_cmds

MKDIR = "mkdir -p {output_dir}"
INSTALL_DEPS_CMD_TMPL = "pip install -q -t {output_dir} --no-cache-dir -r {requirements}"
INSTALL_POETRY_CMD = "pip install poetry --quiet --upgrade pip"
BUILD_PACKAGE_CMD = "poetry build -q"
INSTALL_WHL_CMD_TMPL = "poetry run pip install -q -t {output_dir} --find-links=dist {package_name} --no-cache-dir --upgrade"
INSTALL_WHL_NO_DEPS_CMD_TMPL = "poetry run pip install -q -t {output_dir} --find-links=dist {package_name} --no-cache-dir --no-deps --upgrade"


INSTALL_DEPS_CMD_IN_CONTAINER_TMPL = join_cmds(MKDIR, INSTALL_DEPS_CMD_TMPL)

BUILD_N_INSTALL_CMD_TMPL = join_cmds(
    INSTALL_POETRY_CMD,
    BUILD_PACKAGE_CMD,
    MKDIR,
    INSTALL_WHL_CMD_TMPL
)

BUILD_N_INSTALL_NO_DEPS_CMD_TMPL = join_cmds(
    INSTALL_POETRY_CMD,
    BUILD_PACKAGE_CMD,
    MKDIR,
    INSTALL_WHL_NO_DEPS_CMD_TMPL
)
