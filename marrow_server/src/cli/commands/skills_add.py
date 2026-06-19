import argparse

from cli.commands.base import BaseCommand


class SkillsAddCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "add"

    @property
    def help(self) -> str:
        return "Add a new skill"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        pass
