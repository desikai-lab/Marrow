import argparse

from cli.commands.base import BaseCommand


class SkillsRemoveCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "remove"

    @property
    def help(self) -> str:
        return "Remove a registered skill"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        pass
