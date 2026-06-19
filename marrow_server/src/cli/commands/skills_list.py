import argparse

from cli.commands.base import BaseCommand


class SkillsListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help(self) -> str:
        return "List installed skills"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        pass
