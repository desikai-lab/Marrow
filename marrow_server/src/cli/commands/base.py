import argparse
from abc import ABC, abstractmethod

class BaseCommand(ABC):
    """
    Abstract interface for all CLI commands.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (e.g. 'health', 'migrate')."""
        pass
        
    @property
    @abstractmethod
    def help(self) -> str:
        """Command description for argparse."""
        pass
        
    @abstractmethod
    def register_args(self, parser: argparse.ArgumentParser) -> None:
        """Register CLI arguments for this command."""
        pass
        
    @abstractmethod
    def execute(self, args: argparse.Namespace) -> None:
        """Execute command business logic."""
        pass
