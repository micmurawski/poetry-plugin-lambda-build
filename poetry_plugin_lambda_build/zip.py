from __future__ import annotations

import os
from fnmatch import fnmatch
from functools import reduce
from operator import or_
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_LZMA, ZIP_STORED, ZipFile

compression = {
    "ZIP_STORED": ZIP_STORED,
    "ZIP_DEFLATED": ZIP_DEFLATED,
    "ZIP_BZIP2": ZIP_BZIP2,
    "ZIP_LZMA": ZIP_LZMA,
}


def create_zip_package(dir, output, exclude=None, **kwargs):
    if "compression" in kwargs:
        kwargs["compression"] = compression[kwargs["compression"]]

    if exclude is None:
        # Attempt to make the patterns work cross-platform using os.sep where appropriate
        exclude = [
            f"*{os.sep}__pycache__{os.sep}*",
            f"*{os.sep}__pycache__",
            "__pycache__",
            f"*.pyc",
        ]

    def should_exclude(path, patterns):
        # Calculate both with forward slashes and with os.sep for robust cross-platform matching
        rel_path = os.path.relpath(path, dir)
        rel_path_os = rel_path
        rel_path_fwd = rel_path.replace("\\", "/").replace("/", os.sep) if os.sep != "/" else rel_path

        file_name = os.path.basename(path)
        # Run fnmatch against both forms plus file_name
        for pattern in patterns:
            if fnmatch(rel_path_os, pattern) or fnmatch(rel_path_fwd, pattern) or fnmatch(file_name, pattern):
                return True
        return False

    with ZipFile(output, "w", **kwargs) as zip_file:
        for base_path, _, files in os.walk(dir):
            for file in files:
                file_path = os.path.join(base_path, file)
                if not should_exclude(file_path, exclude):
                    zip_file.write(
                        file_path, 
                        arcname=os.path.relpath(file_path, dir)
                    )
