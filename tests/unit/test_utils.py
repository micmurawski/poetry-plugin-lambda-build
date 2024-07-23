from poetry_plugin_lambda_build.utils import join_cmds, format_cmd

import pytest


def test_join_cmds():
    expected_command = ["mkdir", "-p", "output_dir", "&&", "cd", "output_dir"]
    assert join_cmds(["mkdir", "-p", "output_dir"], ["cd", "output_dir"]) == expected_command

def test_format_cmd_no_replacement():
    cmd = ["echo", "Hello, World!"]
    expected = ["echo", "Hello, World!"]
    assert format_cmd(cmd) == expected

def test_format_cmd_with_replacement():
    cmd = ["echo", "{greeting}", "{name}"]
    expected = ["echo", "Hello,", "World!"]
    assert format_cmd(cmd, greeting="Hello,", name="World!") == expected
