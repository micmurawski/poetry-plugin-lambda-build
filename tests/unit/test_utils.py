from poetry_plugin_lambda_build.utils import format_cmd, join_cmds  # noqa: INP001, D100


def test_join_cmds():  # noqa: ANN201, D103
    expected_command = ["mkdir", "-p", "output_dir", "&&", "cd", "output_dir"]
    assert (
        join_cmds(["mkdir", "-p", "output_dir"], ["cd", "output_dir"])
        == expected_command
    )


def test_format_cmd_no_replacement():  # noqa: ANN201, D103
    cmd = ["echo", "Hello, World!"]
    expected = ["echo", "Hello, World!"]
    assert format_cmd(cmd) == expected


def test_format_cmd_with_replacement():  # noqa: ANN201, D103
    cmd = ["echo", "{greeting}", "{name}"]
    expected = ["echo", "Hello,", "Beautiful", "World!"]
    assert format_cmd(cmd, greeting="Hello,", name=["Beautiful", "World!"]) == expected
