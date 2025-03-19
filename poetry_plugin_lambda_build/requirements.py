from __future__ import annotations

import urllib.parse
from functools import partialmethod
from typing import TYPE_CHECKING

from cleo.io.io import IO
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.utils.utils import create_nested_marker
from poetry.core.version.markers import parse_marker
from poetry.repositories.http_repository import HTTPRepository

from poetry_plugin_lambda_build.walker import (
    get_project_dependency_packages, get_project_dependency_packages2)

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from typing import ClassVar

    from packaging.utils import NormalizedName
    from poetry.poetry import Poetry


class RequirementsExporter:
    """
    RequirementsExporter class to export a lock file to alternative formats.
    """

    FORMAT_CONSTRAINTS_TXT = "constraints.txt"
    FORMAT_REQUIREMENTS_TXT = "requirements.txt"
    ALLOWED_HASH_ALGORITHMS = ("sha256", "sha384", "sha512")

    EXPORT_METHODS: ClassVar[dict[str, str]] = {
        FORMAT_CONSTRAINTS_TXT: "_export_constraints_txt",
        FORMAT_REQUIREMENTS_TXT: "_export_requirements_txt",
    }

    def __init__(self, poetry: Poetry, io: IO, groups: list[str] | None = None) -> None:
        self._poetry = poetry
        self._io = io
        self._with_hashes = True
        self._with_credentials = False
        self._with_urls = True
        self._extras: Collection[NormalizedName] = ()

        if groups:
            self._groups = groups
        else:
            self._groups: Iterable[str] = [MAIN_GROUP]

    @classmethod
    def is_format_supported(cls, fmt: str) -> bool:
        return fmt in cls.EXPORT_METHODS

    def with_extras(self, extras: Collection[NormalizedName]) -> RequirementsExporter:
        self._extras = extras

        return self

    def only_groups(self, groups: Iterable[str]) -> RequirementsExporter:
        self._groups = groups

        return self

    def with_urls(self, with_urls: bool = True) -> RequirementsExporter:
        self._with_urls = with_urls

        return self

    def with_hashes(self, with_hashes: bool = True) -> RequirementsExporter:
        self._with_hashes = with_hashes

        return self

    def with_credentials(self, with_credentials: bool = True) -> RequirementsExporter:
        self._with_credentials = with_credentials

        return self

    def export(self) -> None:
        return self._export_generic_txt(False, False)

    def _export_generic_txt(
        self, with_extras: bool, allow_editable: bool
    ) -> str:
        from poetry.core.packages.utils.utils import path_to_url

        indexes = set()
        content = ""
        dependency_lines = set()

        python_marker = parse_marker(
            create_nested_marker(
                "python_version", self._poetry.package.python_constraint
            )
        )
        if self._poetry.locker.is_locked_groups_and_markers():
            dependency_package_iterator = get_project_dependency_packages2(
                self._poetry.locker,
                project_python_marker=python_marker,
                groups=set(self._groups),
                extras=self._extras,
            )
        else:
            root = self._poetry.package.with_dependency_groups(
                list(self._groups), only=True
            )
            dependency_package_iterator = get_project_dependency_packages(
                self._poetry.locker,
                project_requires=root.all_requires,
                root_package_name=root.name,
                project_python_marker=python_marker,
                extras=self._extras,
            )

        for dependency_package in dependency_package_iterator:
            line = ""

            if not with_extras:
                dependency_package = dependency_package.without_features()

            dependency = dependency_package.dependency
            package = dependency_package.package

            if package.develop and not allow_editable:
                self._io.write_error_line(
                    f"<warning>Warning: {package.pretty_name} is locked in develop"
                    " (editable) mode, which is incompatible with the"
                    " constraints.txt format.</warning>"
                )
                continue

            requirement = dependency.to_pep_508(
                with_extras=False, resolved=True)
            is_direct_local_reference = (
                dependency.is_file() or dependency.is_directory()
            )
            is_direct_remote_reference = dependency.is_vcs() or dependency.is_url()

            if is_direct_remote_reference:
                line = requirement
            elif is_direct_local_reference:
                assert dependency.source_url is not None
                dependency_uri = path_to_url(dependency.source_url)
                if package.develop:
                    line = f"-e {dependency_uri}"
                else:
                    line = f"{package.complete_name} @ {dependency_uri}"
            else:
                line = f"{package.complete_name}=={package.version}"

            if not is_direct_remote_reference and ";" in requirement:
                markers = requirement.split(";", 1)[1].strip()
                if markers:
                    line += f" ; {markers}"

            if (
                not is_direct_remote_reference
                and not is_direct_local_reference
                and package.source_url
            ):
                indexes.add(package.source_url.rstrip("/"))

            if package.files and self._with_hashes:
                hashes = []
                for f in package.files:
                    h = f["hash"]
                    algorithm = "sha256"
                    if ":" in h:
                        algorithm, h = h.split(":")

                        if algorithm not in self.ALLOWED_HASH_ALGORITHMS:
                            continue

                    hashes.append(f"{algorithm}:{h}")

                hashes.sort()

                for h in hashes:
                    line += f" \\\n    --hash={h}"

            dependency_lines.add(line)

        content += "\n".join(sorted(dependency_lines))
        content += "\n"

        if indexes and self._with_urls:
            indexes_header = "".join(self.export_indexes())

            if indexes_header:
                content = indexes_header + "\n" + content
        return content

    _export_constraints_txt = partialmethod(
        _export_generic_txt, with_extras=False, allow_editable=False
    )

    _export_requirements_txt = partialmethod(
        _export_generic_txt, with_extras=True, allow_editable=True
    )

    def export_indexes(self) -> list[str]:
        args = []
        has_pypi_repository = any(
            r.name.lower() == "pypi" for r in self._poetry.pool.all_repositories
        )
        for repository in self._poetry.pool.all_repositories:
            if not isinstance(repository, HTTPRepository):
                continue
            url = repository.authenticated_url
            parsed_url = urllib.parse.urlsplit(url)
            if parsed_url.scheme == "http":
                args += ["--trusted-host", f"{parsed_url.netloc}\n"]
            if (
                not has_pypi_repository
                and repository is self._poetry.pool.repositories[0]
            ):
                args += ["--index-url", f"{url}\n"]
            else:
                args += ["--extra-index-url", f"{url}\n"]
        return args
