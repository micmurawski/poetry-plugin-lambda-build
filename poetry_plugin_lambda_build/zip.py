import os
from fnmatch import fnmatch
from functools import reduce
from operator import or_
from zipfile import ZipFile


def create_zip_package(dir, output, exclude=None):
    if exclude is None:
        exclude = ["*.pyc", "*__pycache__/*"]
    with ZipFile(output, "w") as zip_file:
        for i in os.walk(dir):
            base_path, _, files = i
            for file in files:
                file_path = os.path.join(base_path, file)
                if not reduce(
                    or_, [fnmatch(file_path, pattern) for pattern in exclude]
                ):
                    zip_file.write(file_path, arcname=file_path.replace(dir, ""))
