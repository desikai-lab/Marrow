from .build import BuildCommand
from .diag_index import DiagIndexCommand
from .health import HealthCommand
from .maintenance import MaintenanceCommand
from .migrate import MigrateCommand
from .project_init import InitCommand
from .reindex import ReindexCommand
from .reindex_chunks import ReindexChunksCommand

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
