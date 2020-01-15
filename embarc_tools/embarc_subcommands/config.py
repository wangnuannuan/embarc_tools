from __future__ import print_function, division, unicode_literals
from ..utils import import_submodules
from ..embarc_subcommands import config_subcommands


SUBCOMMANDS = import_submodules(config_subcommands, recursive=False)

help = "Get, set or unset configuration options."

description = ("Currently supported options: bsp, toolchain, build_cfg")


def run(args, remainder=None):
    pass


def setup(subparsers):
    subparser = subparsers.add_parser('config', help=help, description=description)
    subparser.usage = ("\n    embarc config bsp --add <name> <url/path> [<dest>]\n"
                       "    embarc config bsp --rename <oldname> <newname>\n"
                       "    embarc config bsp --remove <name>\n"
                       "    embarc config bsp --list\n"
                       "    embarc config bsp --set <name>\n"
                       "    embarc config toolchain [--version] [--download] gnu\n"
                       "    embarc config toolchain [--version] mw\n"
                       "    embarc config toolchain --set <gnu/mw>\n"
                       "    embarc config build_cfg BOARD <value>\n"
                       "    embarc config build_cfg BD_VER <value>\n"
                       "    embarc config build_cfg CUR_CORE <value>\n")
    subparser.set_defaults(func=run)

    # set up its sub commands
    config_subparsers = subparser.add_subparsers(title="Commands", metavar="           ")
    for _, subcommand in SUBCOMMANDS.items():
        subcommand.setup(config_subparsers)
