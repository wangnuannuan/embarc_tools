#!/usr/bin/env python3
from __future__ import print_function, unicode_literals
import sys
import argparse
from embarc_tools import embarc_subcommands
from embarc_tools.version import __version__
from embarc_tools.utils import import_submodules


SUBCOMMANDS = import_submodules(embarc_subcommands, recursive=False)
ver = __version__


def main():
    parser = argparse.ArgumentParser(
        prog='embarc',
        description='''
            Command-line tool for embARC BSP - https://embarc.org/embarc_bsp\n
            version %s\n\nUse \"embarc <command> -h|--help\" for detailed help.\n
            Online manual and guide available at https://github.com/foss-for-synopsys-dwc-arc-processors/embarc_tools'''
             % ver,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--version", action='version',
        version=__version__,
        help="Display version"
    )
    subparsers = parser.add_subparsers(title="Commands", metavar="           ")

    for _, subcommand in SUBCOMMANDS.items():
        subcommand.setup(subparsers)

    subcommand = SUBCOMMANDS.keys()
    args = None
    if len(sys.argv) == 1:
        return parser.print_help()

    args, remainder = parser.parse_known_args()
    try:
        return args.func(args, remainder)
    except Exception:
        return parser.print_help()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt):
        print("Terminate batch job")
        sys.exit(255)
