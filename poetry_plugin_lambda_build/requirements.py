from __future__ import annotations

import urllib.parse
from collections import defaultdict
from typing import Collection

from cleo.io.io import IO
from packaging.utils import NormalizedName
from poetry.console.exceptions import GroupNotFound
from poetry.core.packages.project_package import ProjectPackage
from poetry.poetry import Poetry
from poetry.repositories.http_repository import HTTPRepository
from poetry_plugin_export.walker import get_project_dependency_packages


class RequirementsExporter:
    ALLOWED_HASH_ALGORITHMS = ("sha256", "sha384", "sha512")

    def __init__(
        self,
        poetry: Poetry,
        io: IO,
        groups: dict[str, set[str]] = {},
        extras: Collection[NormalizedName] = (),
    ) -> None:
        self._poetry = poetry
        self._io = io
        self._validate_group_options(groups)
        self._groups = groups
        self._extras = extras

    @property
    def name(self):
        return self.project_with_activated_groups_only().name

    def project_with_activated_groups_only(self) -> ProjectPackage:
        return self._poetry.package.with_dependency_groups(
            list(self.activated_groups), only=True
        )

    def _validate_group_options(self, group_options: dict[str, set[str]]) -> None:
        """
        Raises an error if it detects that a group is not part of pyproject.toml
        """
        invalid_options = defaultdict(set)
        for opt, groups in group_options.items():
            for group in groups:
                if not self._poetry.package.has_dependency_group(group):
                    invalid_options[group].add(opt)
        if invalid_options:
            message_parts = []
            for group in sorted(invalid_options):
                opts = ", ".join(
                    f"<fg=yellow;options=bold>{opt}</>"
                    for opt in sorted(invalid_options[group])
                )
                message_parts.append(f"{group} (via {opts})")
            raise GroupNotFound(f"Group(s) not found: {', '.join(message_parts)}")

    @property
    def activated_groups(self) -> set[str]:
        return self._groups["only"] or self.non_optional_groups.union(
            self._groups["with"]
        ).difference(self._groups["without"])

    @property
    def non_optional_groups(self) -> set[str]:
        # TODO: this should move into poetry-core
        return {
            group.name
            for group in self._poetry.package._dependency_groups.values()
            if not group.is_optional()
        }

    def _split_dependency_pkg(self, dependency_package, with_extras):
        pkg = dependency_package.clone()

        if not with_extras:
            pkg = pkg.without_features()

        return pkg.dependency, pkg.package

    def _handle_develop_mode(self, package, allow_editable):
        if package.develop:
            if not allow_editable:
                self._io.write_error_line(
                    f"<warning>Warning: {package.pretty_name} is locked in develop"
                    " (editable) mode, which is incompatible with the"
                    " constraints.txt format.</warning>"
                )
                return False
        return True

    def _determine_requirement_line(
        self,
        is_direct_remote_reference,
        is_direct_local_reference,
        requirement,
        package,
        dependency,
    ):
        from poetry.core.packages.utils.utils import path_to_url

        if is_direct_remote_reference:
            return requirement
        elif is_direct_local_reference:
            assert dependency.source_url is not None
            dependency_uri = path_to_url(dependency.source_url)
            return f"{package.complete_name} @ {dependency_uri}"
        else:
            return f"{package.complete_name}=={package.version}"

    def export(
        self,
        with_extras: bool = False,
        allow_editable: bool = True,
        with_hashes: bool = False,
    ) -> str:
        indexes = set()
        content = ""
        dependency_lines = set()

        root = self.project_with_activated_groups_only()

        for dependency_package in get_project_dependency_packages(
            self._poetry.locker,
            project_requires=root.all_requires,
            root_package_name=root.name,
            project_python_marker=root.python_marker,
            extras=self._extras,
        ):
            line = ""

            dependency, package = self._split_dependency_pkg(
                dependency_package, with_extras
            )

            if self._handle_develop_mode(package, allow_editable):
                line += "-e "

            requirement = dependency.to_pep_508(with_extras=False, resolved=True)
            is_direct_local_reference = (
                dependency.is_file() or dependency.is_directory()
            )
            is_direct_remote_reference = dependency.is_vcs() or dependency.is_url()

            line = self._determine_requirement_line(
                is_direct_remote_reference,
                is_direct_local_reference,
                requirement,
                package,
                dependency,
            )

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

            if package.files and with_hashes:
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

        if indexes:
            content = self.export_indexes() + "\n\n" + content

        return content

    def export_indexes(self) -> list[str]:
        args = []
        has_pypi_repository = any(
            r.name.lower() == "pypi" for r in self._poetry.pool.all_repositories
        )
        # Iterate over repositories so that we get the repository with the highest
        # priority first so that --index-url comes before --extra-index-url
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
                args += ["--index-url", url]
            else:
                args += ["--extra-index-url", url]

        return args
