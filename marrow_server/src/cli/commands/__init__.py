from .migrate import MigrateCommand
from .health import HealthCommand
from .reindex import ReindexCommand
from .reindex_chunks import ReindexChunksCommand
from .build import BuildCommand
from .maintenance import MaintenanceCommand
from .project_init import InitCommand
from .diag_index import DiagIndexCommand


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
