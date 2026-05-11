import argparse
import logging
import sys

from cli.commands.base import BaseCommand

logger = logging.getLogger("admin_cli")

class BuildCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "build"
        
    @property
    def help(self) -> str:
        return "Run Build Pipeline"
        
    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument("--build", required=True, help="Template name (without .yaml)")
        parser.add_argument("--verbose", action="store_true", help="Verbose output")
        parser.add_argument(
            "--var",
            action="append",
            metavar="KEY=VALUE",
            default=[],
            help="Template variable (repeatable): --var FEATURE=Auth --var ENV=prod",
        )
        
    def execute(self, args: argparse.Namespace) -> None:

        from tools.builds import run_project_build_logic
        variables: dict[str, str] = {}
        for item in (args.var or []):
            if "=" not in item:
                logger.error("--var requires KEY=VALUE format, got: '%s'", item)
                sys.exit(1)
            k, v = item.split("=", 1)
            variables[k] = v

        logger.info("Starting build: Project='%s', Template='%s'", args.project, args.build)
        try:
            result = run_project_build_logic(
                args.project, args.build, 
                verbose=args.verbose, 
                variables=variables or None
            )
            if result.success:
                print(f"\n[CLI] RESULT: Success. Output: {result.output_path}")
            else:
                logger.error("Build error: %s", result.error)
                sys.exit(1)
        except Exception as e:
            logger.error("Build failed with error: %s", e)
            sys.exit(1)
