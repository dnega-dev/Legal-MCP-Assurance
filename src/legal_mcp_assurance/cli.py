"""Command-line interface for Legal MCP Assurance."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from ._version import VERSION
from .example_data import write_example
from .profiles import get_profile, list_profiles
from .provider import TranscriptFormatError, TranscriptProvider
from .reports import REPORT_FORMATS, render_report
from .runner import AssuranceRunner


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, "{}: error: {}\n".format(self.prog, message))


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="legal-mcp-assurance",
        description="Black-box assurance runner for legal/retrieval tool-server adapters.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(VERSION))
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run an assurance profile against a JSON transcript")
    run.add_argument("--transcript", required=True, help="path to a transcript JSON file")
    run.add_argument("--profile", default="core", help="profile ID (default: core)")
    run.add_argument("--format", choices=REPORT_FORMATS, default="text", dest="report_format")
    run.add_argument("--output", help="write the report to a file instead of standard output")

    profiles = commands.add_parser("profiles", help="inspect built-in assurance profiles")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    profile_list = profile_commands.add_parser("list", help="list built-in profiles")
    profile_list.add_argument("--format", choices=("text", "json"), default="text", dest="list_format")
    profile_show = profile_commands.add_parser("show", help="show profile requirements")
    profile_show.add_argument("profile", help="profile ID")
    profile_show.add_argument("--format", choices=("text", "json"), default="text", dest="show_format")

    init = commands.add_parser("init", help="write local starter assets")
    init_commands = init.add_subparsers(dest="init_command", required=True)
    example = init_commands.add_parser("example", help="write an example JSON transcript")
    example.add_argument("path", nargs="?", default="legal-mcp-transcript.json")
    example.add_argument("--broken", action="store_true", help="write a deliberately failing example")
    example.add_argument("--force", action="store_true", help="overwrite an existing destination")
    return parser


def _write_output(content: str, output: Optional[str]) -> None:
    if output is None or output == "-":
        sys.stdout.write(content)
        return
    with Path(output).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _run(args: argparse.Namespace) -> int:
    try:
        profile = get_profile(args.profile)
    except KeyError:
        available = ", ".join(profile.id for profile in list_profiles())
        sys.stderr.write("error: unknown profile {!r}; available: {}\n".format(args.profile, available))
        return 2
    try:
        provider = TranscriptProvider.from_file(args.transcript)
        result = AssuranceRunner().run(profile, provider)
        _write_output(render_report(result, args.report_format), args.output)
    except (TranscriptFormatError, OSError, ValueError) as exc:
        sys.stderr.write("error: {}\n".format(exc))
        return 2
    return 0 if result.successful else 1


def _profiles_list(args: argparse.Namespace) -> int:
    profiles = list_profiles()
    if args.list_format == "json":
        sys.stdout.write(json.dumps([profile.to_dict(False) for profile in profiles], indent=2, sort_keys=True) + "\n")
    else:
        for profile in profiles:
            sys.stdout.write("{}\t{}\t{} checks\n".format(profile.id, profile.title, len(profile.checks)))
    return 0


def _profiles_show(args: argparse.Namespace) -> int:
    try:
        profile = get_profile(args.profile)
    except KeyError:
        sys.stderr.write("error: unknown profile {!r}\n".format(args.profile))
        return 2
    if args.show_format == "json":
        sys.stdout.write(json.dumps(profile.to_dict(True), indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write("{} ({})\n{}\n\n".format(profile.title, profile.id, profile.description))
        for check in profile.checks:
            sys.stdout.write("{}  {}\n    {}\n".format(check.id, check.title, check.requirement))
    return 0


def _init_example(args: argparse.Namespace) -> int:
    try:
        write_example(args.path, broken=args.broken, force=args.force)
    except (OSError, ValueError) as exc:
        sys.stderr.write("error: {}\n".format(exc))
        return 2
    sys.stdout.write("wrote {}\n".format(args.path))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "profiles" and args.profiles_command == "list":
        return _profiles_list(args)
    if args.command == "profiles" and args.profiles_command == "show":
        return _profiles_show(args)
    if args.command == "init" and args.init_command == "example":
        return _init_example(args)
    raise AssertionError("unreachable command dispatch")
