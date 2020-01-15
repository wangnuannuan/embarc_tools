from __future__ import print_function, division, unicode_literals
from ...notify import print_string
from ...settings import embARC

help = "Set global build configuration."
usage = ("\n    embarc config build_cfg BOARD <value>\n"
         "    embarc config build_cfg BD_VER <value>\n"
         "    embarc config build_cfg CUR_CORE <value>\n")


def run(args, remainder=None):
    if len(remainder) != 2:
        print("usage: " + usage)
    else:
        config = remainder[0]
        if config not in ["BOARD", "BD_VER", "CUR_CORE"]:
            print("usage: " + usage)
            return
        value = remainder[1]
        embarc_obj = embARC()
        print_string("Set %s = %s as global setting" % (config, value))
        embarc_obj.set_global(config, value)


def setup(subparsers):
    subparser = subparsers.add_parser('build_cfg', help=help)
    subparser.usage = usage
    subparser.set_defaults(func=run)
