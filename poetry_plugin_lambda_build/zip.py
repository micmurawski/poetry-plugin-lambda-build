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
        exclude = ["*.pyc", "*__pycache__/*"]

    with ZipFile(output, "w", **kwargs) as zip_file:
        for i in os.walk(dir):
            base_path, _, files = i
            for file in files:
                file_path = os.path.join(base_path, file)

                if not reduce(
                    or_, [fnmatch(file_path, pattern) for pattern in exclude], False
                ):
                    zip_file.write(file_path, arcname=file_path.replace(dir, ""))
