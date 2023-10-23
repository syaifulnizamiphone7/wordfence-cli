import importlib
from types import ModuleType
from typing import Optional, Dict, Set

from .config.typing import ConfigDefinitions
from .config.config_items import config_definitions_to_config_map, \
        ConfigItemDefinition
from .context import CliContext

VALID_SUBCOMMANDS = {
        'configure',
        'scan',
        'vuln-scan',
        'help'
    }


def map_subcommand_to_module_name(subcommand: str) -> str:
    return subcommand.replace('-', '')


def import_subcommand_module(
            subcommand: str,
            submodule: Optional[str] = None
        ) -> ModuleType:
    name = map_subcommand_to_module_name(subcommand)
    if submodule is None:
        submodule = name
    target = f'.{name}.{submodule}'
    return importlib.import_module(
            target,
            package='wordfence.cli'
        )


class Subcommand:

    def __init__(self, context: CliContext):
        self.context = context
        # Aliases for shorter access to context properties
        self.config = context.config
        self.cache = context.cache

    def invoke(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def generate_exception_message(
                self,
                exception: BaseException
            ) -> Optional[str]:
        return None


class SubcommandDefinition:

    def __init__(
                self,
                name: str,
                description: str,
                config_definitions: ConfigDefinitions,
                config_section: str,
                cacheable_types: Set[str],
                requires_config: bool = True
            ):
        self.name = name
        self.description = description
        self.config_definitions = config_definitions
        self.config_section = config_section
        self.config_map = None
        self.cacheable_types = cacheable_types
        self.requires_config = requires_config

    def get_config_map(self) -> Dict[str, ConfigItemDefinition]:
        if self.config_map is None:
            self.config_map = config_definitions_to_config_map(
                    self.config_definitions
                )
        return self.config_map

    def accepts_option(self, name: str) -> bool:
        return name in self.config_definitions

    def initialize_subcommand(self, context: CliContext) -> Subcommand:
        module = import_subcommand_module(self.name)
        assert hasattr(module, 'factory')
        assert callable(module.factory)
        subcommand = module.factory(context)
        assert isinstance(subcommand, Subcommand)
        return subcommand


def load_subcommand_definition(subcommand: str) -> SubcommandDefinition:
    module = import_subcommand_module(subcommand, 'definition')
    assert hasattr(module, 'definition')
    assert isinstance(module.definition, SubcommandDefinition)
    return module.definition


def load_subcommand_definitions() -> Dict[str, SubcommandDefinition]:
    definitions = dict()
    for subcommand in VALID_SUBCOMMANDS:
        definitions[subcommand] = load_subcommand_definition(subcommand)
    return definitions
