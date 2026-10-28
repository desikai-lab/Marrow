from migrator.base import Migration

from .v1_to_v2_history_folder_scheme import V1ToV2HistoryFolderScheme
from .v2_to_v3_add_init_agent import V2ToV3AddInitAgent

REGISTRY: list[Migration] = [
    V1ToV2HistoryFolderScheme(),
    V2ToV3AddInitAgent(),
]
