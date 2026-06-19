from .build import BuildCommand
from .diag_index import DiagIndexCommand
from .health import HealthCommand
from .maintenance import MaintenanceCommand
from .migrate import MigrateCommand
from .project_init import InitCommand
from .reindex import ReindexCommand
from .reindex_chunks import ReindexChunksCommand
from .skills_add import SkillsAddCommand
from .skills_list import SkillsListCommand
from .skills_remove import SkillsRemoveCommand
from .skills_update import SkillsUpdateCommand

COMMANDS = [
    MigrateCommand(),
    HealthCommand(),
    ReindexCommand(),
    ReindexChunksCommand(),
    BuildCommand(),
    MaintenanceCommand(),
    InitCommand(),
    DiagIndexCommand(),
]

SKILLS_COMMANDS = [
    SkillsAddCommand(),
    SkillsListCommand(),
    SkillsUpdateCommand(),
    SkillsRemoveCommand(),
]
