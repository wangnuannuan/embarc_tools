from __future__ import print_function, division, unicode_literals
import os
from ...notify import print_string
from ...settings import EMBARC_BSP_URL
from ...settings import embARC
from ...utils import getcwd, read_json, unzip
import git
from git.util import RemoteProgress


help = "Get, set or unset embarc-root configuration."

usage = ("\n    embarc config embarc-root --add <name> <url/path> [<dest>]\n"
         "    embarc config embarc-root --set <name>\n"
         "    embarc config embarc-root --rename <oldname> <newname>\n"
         "    embarc config embarc-root --remove <name>\n"
         "    embarc config embarc-root --list")


def run(args, remainder=None):
    embarc_obj = embARC()
    num = [args.add, args.rename, args.remove]
    if num.count(False) + num.count(None) < 2:
        print("usage: " + usage)
        return
    if args.add:
        if len(remainder) < 2:
            print("usage: " + usage)
            return
        else:
            name = remainder[0]
            url = remainder[1]
            dest = None
            if len(remainder) >= 3:
                dest = remainder[2]
                if not (os.path.exists(url) and os.path.isdir(url)):
                    print_string("% is not a valid path" % dest)
                    dest = None
            if os.path.exists(url) and os.path.isdir(url):
                source_type = "local"
                url = os.path.abspath(url)
                msg = "Add this local (%s) to user profile embarc.json" % (url)
                print_string(msg)
                embarc_obj.set_path(name, source_type, url)
                args.list = True

            elif os.path.exists(url) and os.path.isfile(url):
                if url.endswith("zip"):
                    dest_dir = dest if dest else getcwd()
                    path = os.path.join(dest_dir, name)
                    result = unzip(url, name)
                    if not result:
                        msg = "Unzip zip failed"
                        print_string(msg, level="error")
                    else:
                        source_type = "zip"
                        embarc_obj.set_path(name, source_type, path, url)
                        print_string("Add (%s) to user profile embarc.json" % path)
                        args.list = True
            elif url == EMBARC_BSP_URL:
                if not os.path.exists(name):
                    path = dest if dest else getcwd()
                    print_string("Start clone {}".format(url))
                    git.Repo.clone_from(url, os.path.join(path, name), RemoteProgress())
                    source_type = "git"
                    embarc_obj.set_path(name, source_type, os.path.join(path, name), url)
                    print_string("Add (%s) to user profile embarc.json" % os.path.join(path, name))
                    args.list = True
                else:
                    print_string("There is already a folder or file named '%s' under current path" % name)
                    return
            else:
                print("usage: " + usage)
                return
    elif args.rename:
        if len(remainder) != 2:
            print("usage: " + usage)
        else:
            old = remainder[0]
            new = remainder[1]
            print_string("Start rename {} to {}".format(old, new))
            embarc_obj.rename(old, new)
            args.list = True
    elif args.remove:
        name = args.remove
        print_string("Start remove {} ".format(name))
        embarc_obj.remove_path(name)
        args.list = True
    elif args.set:
        name = args.set
        print_string("Set %s as global EMBARC_ROOT" % name)
        if embarc_obj.get_path(name):
            config = "EMBARC_ROOT"
            embarc_obj.set_global(config, name)
        else:
            print_string("This is not a valid embarc root")
            args.list = True
    else:
        if remainder:
            print("usage: " + usage)
            return

    if args.list:
        print_string("Current recored embARC source code")
        current_paths = embarc_obj.list_path()
        makefile = embarc_obj.get_makefile(getcwd())
        app_setting = dict()
        embarc_root = None
        if makefile:
            if os.path.exists("embarc_app.json"):
                app_setting = read_json("embarc_app.json")
                embarc_root = app_setting.get("EMBARC_ROOT", False)
            else:
                _, app_setting = embarc_obj.get_makefile_config(app_setting)
                embarc_root = app_setting.get("EMBARC_ROOT", False)
        if current_paths:
            embarc_obj.list_path(show=True, current=embarc_root)


def setup(subparsers):
    subparser = subparsers.add_parser('embarc-root', help=help)
    subparser.usage = usage
    mutualex_group = subparser.add_mutually_exclusive_group()
    mutualex_group.add_argument(
        "--add", action='store_true', help='fetch the remote source code and add it to embarc.json')
    mutualex_group.add_argument(
        '-s', '--set', help="set a global EMBARC_ROOT, make sure you have added it to embarc.json", metavar='')
    mutualex_group.add_argument(
        "--rename", action='store_true', help="rename embarc source code")
    mutualex_group.add_argument(
        '-rm', '--remove', help="remove the specified embarc source code", metavar='')
    subparser.add_argument(
        '-l', '--list', action='store_true', help="show all recored embARC embarc source code")
    subparser.set_defaults(func=run)
