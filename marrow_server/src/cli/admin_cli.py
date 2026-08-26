import argparse
import logging
import os
import sys

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, TypeError):
        pass

# Add project root and src to module search path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
server_root = os.path.dirname(src_dir)
monorepo_root = os.path.dirname(server_root)

for d in (monorepo_root, server_root, src_dir):
    if d in sys.path:
        sys.path.remove(d)
    sys.path.insert(0, d)


# Logging setup
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("admin_cli")

from cli.commands import COMMANDS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Admin CLI: Marrow management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Make command required (for Python 3.7+ required=True)
    subparsers.required = True

    command_map = {}
    for cmd in COMMANDS:
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help)
        cmd.register_args(cmd_parser)
        command_map[cmd.name] = cmd

    args = parser.parse_args()

    # Launch execute for the selected command
    if args.command in command_map:
        command_map[args.command].execute(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
