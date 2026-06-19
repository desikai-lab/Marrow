import argparse
import logging
import os
import sys

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, TypeError):
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("skills_cli")

from cli.commands.skills_add import SkillsAddCommand  # noqa: E402
from cli.commands.skills_list import SkillsListCommand  # noqa: E402
from cli.commands.skills_remove import SkillsRemoveCommand  # noqa: E402
from cli.commands.skills_update import SkillsUpdateCommand  # noqa: E402

SKILLS_COMMANDS = [
    SkillsAddCommand(),
    SkillsListCommand(),
    SkillsUpdateCommand(),
    SkillsRemoveCommand(),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skills CLI: Manage Marrow project skills")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    subparsers.required = True
    command_map = {}
    for cmd in SKILLS_COMMANDS:
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help)
        cmd.register_args(cmd_parser)
        command_map[cmd.name] = cmd
    args = parser.parse_args()
    if args.command in command_map:
        command_map[args.command].execute(args)
    else:
        parser.print_help()
