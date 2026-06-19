import argparse

from cli.commands.base import BaseCommand


class SkillsUpdateCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "update"

    @property
    def help(self) -> str:
        return "Update an existing skill"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        pass
