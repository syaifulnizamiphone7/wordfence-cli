from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Union, Set

from ..util.versioning import PhpVersion, compare_php_versions
from ..wordpress.site import WordpressSite
from ..wordpress.extension import Extension
from ..wordpress.plugin import Plugin
from ..wordpress.theme import Theme


VERSION_ANY = '*'


@dataclass
class VersionRange:
    from_version: str
    from_inclusive: bool
    to_version: str
    to_inclusive: bool

    def includes(self, version: Union[PhpVersion, str]) -> bool:
        from_result = compare_php_versions(self.from_version, version)
        if not (self.from_version == VERSION_ANY or
                from_result == -1 or
                (self.from_inclusive and from_result == 0)):
            return False
        to_result = compare_php_versions(self.to_version, version)
        if not (self.to_version == VERSION_ANY or
                to_result == 1 or
                (self.to_inclusive and to_result == 0)):
            return False
        return True


class SoftwareType(str, Enum):
    CORE = 'core'
    PLUGIN = 'plugin'
    THEME = 'theme'


@dataclass
class Software:
    type: SoftwareType
    name: str
    slug: str
    affected_versions: Dict[str, VersionRange] = field(default_factory=dict)
    patched: bool = False
    patched_versions: List[str] = field(default_factory=list)


@dataclass
class Copyright:
    notice: str
    license: str
    license_url: str


@dataclass
class CopyrightInformation:
    message: Optional[str] = None
    copyrights: Dict[str, Copyright] = field(default_factory=dict)


@dataclass
class Vulnerability:
    identifier: str
    title: str
    software: List[Software] = field(default_factory=list)
    informational: bool = False
    references: List[str] = field(default_factory=list)
    published: Optional[str] = None
    copyright_information: Optional[CopyrightInformation] = None


@dataclass
class ScannerVulnerability(Vulnerability):
    pass


@dataclass
class Cwe:
    identifier: int
    name: str
    description: str


@dataclass
class Cvss:
    vector: str
    score: Union[float, int]
    rating: str


@dataclass
class ProductionSoftware(Software):
    remediation: str = ''


@dataclass
class ProductionVulnerability(Vulnerability):
    software: List[ProductionSoftware] = field(default_factory=list)
    description: str = ''
    cwe: Optional[Cwe] = None
    cvss: Optional[Cvss] = None
    cve: Optional[str] = None
    cve_link: Optional[str] = None
    researchers: List[str] = field(default_factory=list)
    updated: Optional[str] = None


SLUG_WORDPRESS = 'wordpress'


class VulnerabilityIndex:

    def __init__(self, vulnerabilities: Dict[str, Vulnerability]):
        self.vulnerabilities = vulnerabilities
        self._initialize_index(vulnerabilities)

    def _add_vulnerability_to_index(
                self,
                vulnerability: Vulnerability
            ) -> None:
        for software in vulnerability.software:
            type_index = self.index[software.type]
            if software.slug not in type_index:
                type_index[software.slug] = []
            software_index = type_index[software.slug]
            for version_range in software.affected_versions.values():
                software_index.append(
                        (
                            version_range,
                            vulnerability.identifier
                        )
                    )

    def _initialize_index(self, vulnerabilities: Dict[str, Vulnerability]):
        self.index = {}
        for type in SoftwareType:
            self.index[type] = {}
        for vulnerability in vulnerabilities.values():
            self._add_vulnerability_to_index(vulnerability)

    def get_vulnerabilities(
                self,
                software_type: SoftwareType,
                slug: str,
                version: str
            ) -> Dict[str, Vulnerability]:
        vulnerabilities = {}
        type_index = self.index[software_type]
        if slug in type_index:
            software_index = type_index[slug]
            for version_range, identifier in software_index:
                if version_range.includes(version):
                    vulnerabilities[identifier] = \
                            self.vulnerabilities[identifier]
        return vulnerabilities

    def get_core_vulnerabilties(
                self,
                version: str
            ) -> Dict[str, Vulnerability]:
        return self.get_vulnerabilities(
                SoftwareType.CORE,
                SLUG_WORDPRESS,
                version
            )

    def get_plugin_vulnerabilities(
                self,
                slug: str,
                version: str
            ) -> Dict[str, Vulnerability]:
        return self.get_vulnerabilities(
                SoftwareType.PLUGIN,
                slug,
                version
            )

    def get_theme_vulnerabilities(
                self,
                slug: str,
                version: str
            ) -> Dict[str, Vulnerability]:
        return self.get_vulnerabilities(
                SoftwareType.THEME,
                slug,
                version
            )


@dataclass
class ScannableSoftware:
    type: SoftwareType
    slug: str
    version: str


class VulnerabilityFilter:

    def __init__(
                self,
                excluded: Set[str],
                included: Set[str],
                informational: bool = False
            ):
        self.excluded = excluded
        self.included = included
        self.informational = informational

    def allows(self, vulnerability: Vulnerability) -> bool:
        if vulnerability.identifier in self.excluded:
            return False
        if len(self.included) and \
                vulnerability.identifier not in self.included:
            return False
        if vulnerability.informational and not self.informational:
            return False
        return True

    def filter(
                self,
                vulnerabilities: Dict[str, Vulnerability]
            ) -> Dict[str, Vulnerability]:
        return {
                identifier: vulnerability for identifier, vulnerability
                in vulnerabilities.items() if self.allows(vulnerability)
            }


DEFAULT_FILTER = VulnerabilityFilter(
        excluded={},
        included={},
        informational=False
    )


class VulnerabilityScanner:

    def __init__(
                self,
                index: VulnerabilityIndex,
                filter: VulnerabilityFilter = DEFAULT_FILTER
            ):
        self.index = index
        self.filter = filter
        self.vulnerabilities = {}
        self.affected = {}

    def scan(self, software: ScannableSoftware) -> Dict[str, Vulnerability]:
        vulnerabilities = self.index.get_vulnerabilities(
                software.type,
                software.slug,
                software.version
            )
        vulnerabilities = self.filter.filter(vulnerabilities)
        self.vulnerabilities.update(vulnerabilities)
        for identifier in vulnerabilities:
            if identifier not in self.affected:
                self.affected[identifier] = []
            self.affected[identifier].append(software)
        return vulnerabilities

    def scan_core(self, version: str) -> Dict[str, Vulnerability]:
        return self.scan(
                ScannableSoftware(
                    type=SoftwareType.CORE,
                    slug=SLUG_WORDPRESS,
                    version=version
                )
            )

    def scan_site(self, site: WordpressSite) -> Dict[str, Vulnerability]:
        return self.scan_core(site.get_version())

    def scan_extension(
                self,
                extension: Extension,
                type: SoftwareType
            ) -> Dict[str, Vulnerability]:
        return self.scan(
                ScannableSoftware(
                    type=type,
                    slug=extension.slug,
                    version=extension.version
                )
            )

    def scan_plugin(self, plugin: Plugin) -> Dict[str, Vulnerability]:
        return self.scan_extension(plugin, SoftwareType.PLUGIN)

    def scan_theme(self, theme: Theme) -> Dict[str, Vulnerability]:
        return self.scan_extension(theme, SoftwareType.THEME)

    def get_vulnerability_count(self) -> int:
        return len(self.vulnerabilities)

    def get_affected_count(self) -> int:
        count = 0
        for affected in self.affected.values():
            count += len(affected)
        return count
