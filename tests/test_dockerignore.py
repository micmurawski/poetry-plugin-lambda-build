import os
import tempfile

from poetry_plugin_lambda_build.docker import _should_ignore, _read_dockerignore_file


def test_should_ignore_with_no_patterns():
    """Test that no files are ignored when no patterns are provided."""
    assert not _should_ignore("test.txt")
    assert not _should_ignore("test.py")
    assert not _should_ignore("test/foo.txt")


def test_should_ignore_with_patterns():
    """Test that files are correctly ignored based on patterns."""
    patterns = ["*.pyc", "__pycache__", "*.git*"]

    # Should be ignored
    assert _should_ignore("test.pyc", patterns)
    assert _should_ignore("__pycache__/test.py", patterns)
    assert _should_ignore(".git/config", patterns)
    assert _should_ignore("test/.gitignore", patterns)

    # Should not be ignored
    assert not _should_ignore("test.py", patterns)
    assert not _should_ignore("test.txt", patterns)
    assert not _should_ignore("test/foo.txt", patterns)


def test_read_dockerignore_file_empty():
    """Test reading an empty dockerignore file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("")

    try:
        patterns = _read_dockerignore_file(f.name)
        assert patterns == []
    finally:
        os.unlink(f.name)


def test_read_dockerignore_file_with_patterns():
    """Test reading a dockerignore file with patterns."""
    content = """
# This is a comment
*.pyc
__pycache__/
*.git*
# Another comment
.env
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)

    try:
        patterns = _read_dockerignore_file(f.name)
        assert patterns == ["*.pyc", "__pycache__/", "*.git*", ".env"]
    finally:
        os.unlink(f.name)


def test_read_dockerignore_file_nonexistent():
    """Test reading a nonexistent dockerignore file."""
    patterns = _read_dockerignore_file("nonexistent_file")
    assert patterns == []


def test_read_dockerignore_file_with_empty_lines():
    """Test reading a dockerignore file with empty lines."""
    content = """
*.pyc

__pycache__/

*.git*

.env
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)

    try:
        patterns = _read_dockerignore_file(f.name)
        assert patterns == ["*.pyc", "__pycache__/", "*.git*", ".env"]
    finally:
        os.unlink(f.name)


def test_should_ignore_with_complex_patterns():
    """Test that complex patterns are correctly handled."""
    patterns = [
        "*.pyc",
        "**/*.pyc",
        "**/__pycache__/**",
        "**/.git/**",
        "**/node_modules/**",
        "**/*.log"
    ]

    # Should be ignored
    assert _should_ignore("test.pyc", patterns)
    assert _should_ignore("foo/bar/test.pyc", patterns)
    assert _should_ignore("foo/__pycache__/bar.py", patterns)
    assert _should_ignore("foo/bar/.git/config", patterns)
    assert _should_ignore("foo/node_modules/bar", patterns)
    assert _should_ignore("foo/bar.log", patterns)

    # Should not be ignored
    assert not _should_ignore("test.py", patterns)
    assert not _should_ignore("foo/bar/test.txt", patterns)
    assert not _should_ignore("foo/bar/baz.py", patterns)
