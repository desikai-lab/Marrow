from migrator.base import Migration

from .v1_to_v2_history_folder_scheme import V1ToV2HistoryFolderScheme

REGISTRY: list[Migration] = [
    V1ToV2HistoryFolderScheme(),
]
