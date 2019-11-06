from __future__ import print_function, unicode_literals
import sys
import os
import time
import collections
from prettytable import PrettyTable
from elftools.elf.elffile import ELFFile
from ..settings import BUILD_CONFIG_TEMPLATE, BUILD_OPTION_NAMES, BUILD_INFO_NAMES, BUILD_CFG_NAMES, BUILD_SIZE_SECTION_NAMES, get_config, MAKEFILENAMES
from ..utils import mkdir, getcwd, delete_dir_files, cd, generate_json, pquery, pqueryOutputinline, pqueryTemporaryFile
from ..notify import (print_string, print_table)
from ..osp import osp
from ..builder import secureshield


class embARC_Builder(object):
    def __init__(self, osproot=None, buildopts=None, outdir=None, config_file="embarc_app.json"):
        self.buildopts = dict()
        make_options = ' '
        if osproot is not None and os.path.isdir(osproot):
            self.osproot = os.path.realpath(osproot)
        else:
            self.osproot = None
        if outdir is not None:
            self.outdir = os.path.realpath(outdir)
            make_options += 'OUT_DIR_ROOT=' + str(self.outdir) + ' '
        else:
            self.outdir = None

        if buildopts is not None:
            self.buildopts.update(buildopts)
        # self.make_options = make_options
        self.config_file = config_file

    @staticmethod
    def is_embarc_makefile(app):
        with open(app) as f:
            embarc_root = False
            appl = False
            lines = f.read().splitlines()
            for line in lines:
                if "EMBARC_ROOT" in line:
                    embarc_root = True
                if "APPL" in line:
                    appl = True
                if embarc_root and appl:
                    return True
            return False

    @staticmethod
    def build_common_check(app):
        build_status = {'result': True, 'reason': ''}
        app_normpath = os.path.normpath(app)
        if not os.path.isdir(app_normpath):
            build_status['reason'] = 'Application folder doesn\'t exist!'
            build_status['result'] = False
        current_makefile = None
        for makename in MAKEFILENAMES:
            if makename in os.listdir(app_normpath):
                current_makefile = os.path.join(app_normpath, makename)
                break
        if not current_makefile:
            build_status['reason'] = 'Application makefile donesn\'t exist!'
            build_status['result'] = False
        else:
            if not embARC_Builder.is_embarc_makefile(current_makefile):
                build_status['reason'] = 'Application makefile is invalid!'
                build_status['result'] = False

        app_realpath = os.path.realpath(app_normpath)
        build_status['app_path'] = app_realpath

        return app_realpath, build_status

    def configCoverity(self, toolchain):
        print_string("Config coverity")
        build_status = {'result': True, 'reason': ''}
        self.coverity_comptype = 'gcc'
        self.coverity_compiler = 'arc-elf32-gcc'
        if toolchain == "gnu":
            pass
        elif toolchain == "mw":
            self.coverity_comptype = 'clangcc'
            self.coverity_compiler = 'ccac'
        else:
            build_status["result"] = False
            build_status["reason"] = "Toolchian is not supported!"
            return build_status
        self.coverity_sa_version = os.environ.get("COVERITY_SA_VERSION", None)
        self.coverity_server = os.environ.get("COVERITY_SERVER", None)
        self.user = os.environ.get("AUTO_USER", None)
        self.password = os.environ.get("AUTO_PASSWORD", None)
        self.coverity_steam_pre = os.environ.get("COVERITY_STREAM_PRE", None)
        return build_status

    def _setCoverityDirs(self, app):
        app_path_list = app.split("/")
        self.coverity_steam = self.coverity_steam_pre + "_".join(app_path_list[1:])
        # print_string("The coverity stream: {} {} {} ".format(self.coverity_steam))
        self.coverity_data_dir = os.environ.get("COVERITY_DATA_DIR", "coverity-data")
        self.coverity_config = os.path.join(self.coverity_data_dir, "coverity-config.xml")
        self.coverity_html = "coverity_html"
        if os.path.exists(self.coverity_data_dir):
            delete_dir_files(self.coverity_data_dir, dir=True)
            mkdir(self.coverity_data_dir)
        if os.path.exists(self.coverity_html):
            delete_dir_files(self.coverity_html, dir=True)
    
    def _output_reader(self, proc):
        output_file = self.apppath + "/build.log"
        log_out_fp = open(output_file, "wt")
        for line in iter(proc.stdout.readline, b''):
            line_str = line.decode('utf-8')
            log_out_fp.write(line_str)
            log_out_fp.flush()
            print(line_str, end="")
        log_out_fp.close()

    def build_coverity(self, make_cmd):
        build_status = {'result': True, 'reason': ''}
        print_string("BEGIN SECTION Configure Coverity to use the built-incompiler")
        config_compilercmd = [
            "cov-configure",
            "--config",
            self.coverity_config,
            "--template",
            "--comptype",
            self.coverity_comptype,
            "--compiler",
            self.coverity_compiler
        ]
        returnstatus = pquery(config_compilercmd, output_callback=self._output_reader)
        if not returnstatus:
            build_status["result"] = False
            build_status["reason"] = "Configure Coverity Failed!"
            return build_status

        print_string("BEGIN SECTION Build with Coverity {}".format(self.coverity_sa_version))
        coverity_buildcmd = [
            "cov-build",
            "--config",
            self.coverity_config,
            "--dir",
            self.coverity_data_dir,
        ]
        coverity_buildcmd.extend(make_cmd)
        returnstatus = pquery(coverity_buildcmd, output_callback=self._output_reader)
        if not returnstatus:
            build_status["result"] = False
            build_status["reason"] = "Build with Coverity Failed!"
            return build_status

        print_string("BEGIN SECTION Coverity Analyze Defects")
        coverity_analyzecmd = [
            "cov-analyze",
            "--dir",
            self.coverity_data_dir
        ]
        returnstatus = pquery(coverity_analyzecmd, output_callback=self._output_reader)
        if not returnstatus:
            build_status["result"] = False
            build_status["reason"] = "Coverity Analyze Defects Failed!"
            return build_status

        print_string("BEGIN SECTION Coverity Format Errors into HTML")
        coverity_errorscmd = [
            "cov-format-errors",
            "--dir", self.coverity_data_dir,
            "-x", "-X",
            "--html-output", self.coverity_html
        ]
        returnstatus = pquery(coverity_errorscmd, output_callback=self._output_reader)
        if not returnstatus:
            build_status["result"] = False
            build_status["reason"] = "Coverity Format Errors into HTML Failed!"
            return build_status

        print_string("BEGIN SECTION Coverity Commit defects to {} steam {}".format(self.coverity_server, self.coverity_steam))
        coverity_commitcmd = [
            "cov-commit-defects",
            "--dir", self.coverity_data_dir,
            "--host", self.coverity_server,
            "--stream", self.coverity_steam,
            "--user", self.user,
            "--password", self.password
        ]
        returnstatus = pquery(coverity_commitcmd, output_callback=self._output_reader)
        if not returnstatus:
            build_status["result"] = False
            build_status["reason"] = "Coverity Commit defects Failed!"
            return build_status

        return build_status

    def get_build_cmd(self, app, target=None, parallel=8, silent=False):
        build_status = dict()
        build_cmd = ["make"]
        if parallel:
            build_cmd.extend(["-j", str(parallel)])
        if target != "info":
            with cd(app):
                self.get_makefile_config(self.get_build_template())
        build_cmd.extend(self.make_options)
        if silent:
            if "SILENT=1" not in build_cmd:
                build_cmd.append("SILENT=1")
        if isinstance(target, str) or target is not None:
            build_cmd.append(target)
        else:
            build_status['reason'] = "Unrecognized build target"
            build_status['result'] = False
            return build_status
        build_cmd_str = " ".join(build_cmd)
        print_string("Build command: {} ".format(build_cmd_str))
        build_status['build_cmd'] = build_cmd
        return build_status

    def build_target(self, app, target=None, parallel=8, coverity=False, silent=False):
        app_realpath, build_status = self.build_common_check(app)
        build_status['build_target'] = target
        build_status['time_cost'] = 0
        print_string("Build target: {} " .format(target))

        if not build_status['result']:
            return build_status
        self.apppath = app
        # Check and create output directory
        if (self.outdir is not None) and (not os.path.isdir(self.outdir)):
            print_string("Create application output directory: " + self.outdir)
            os.makedirs(self.outdir)

        current_build_status = self.get_build_cmd(app_realpath, target, parallel, silent)
        build_status.update(current_build_status)
        build_cmd = build_status.get('build_cmd', None)

        def start_build(build_cmd, build_status=None):
            print_string("Start to build application")
            time_pre = time.time()
            if coverity:
                with cd(app_realpath):
                    self._setCoverityDirs(app)
                    coverity_build_status = self.build_coverity(build_cmd)
                    if not coverity_build_status["result"]:
                        build_status["result"] = False
                        build_status["reason"] = coverity_build_status["reason"]
                        build_status["build_msg"] = coverity_build_status["build_msg"]
                    else:
                        build_status["build_msg"] = ["Build Coverity successfully"]
            else:
                try:
                    returnstatus = pquery(build_cmd, output_callback=self._output_reader, cwd=app)
                    build_status['result'] = returnstatus
                except (KeyboardInterrupt):
                    print_string("Terminate batch job", "warning")
                    sys.exit(1)
                except Exception as e:
                    print("Run command({}) failed! {} ".format(" ".join(build_cmd), e))
                    build_status["build_msg"] = ["Build failed"]
                    build_status["reason"] = "ProcessError: Run command {} failed".format(build_cmd)
                    build_status['result'] = False
            build_status['time_cost'] = (time.time() - time_pre)
            return build_status

        secureshield_config = secureshield.common_check(
            self.buildopts["TOOLCHAIN"], self.buildopts["BOARD"], app_realpath)
        if secureshield_config:
            with secureshield.secureshield_appl_cfg_gen(self.buildopts["TOOLCHAIN"], secureshield_config, app_realpath):
                build_cmd_list = build_cmd.split()
                target = build_cmd_list[-1]
                build_cmd_list[-1] = "USE_SECURESHIELD_APPL_GEN=1"
                build_cmd_list.append(target)
                build_cmd = " ".join(build_cmd_list)
                build_status = start_build(build_cmd, build_status)
        else:
            build_status = start_build(build_cmd, build_status)
        print_string("Completed in: ({})s  ".format(build_status['time_cost']))
        return build_status

    def build_elf(self, app, parallel=False, pre_clean=False, post_clean=False, silent=False):
        # Clean Application before build if requested
        if pre_clean:
            build_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not build_status['result']:
                return build_status

        # Build Application
        build_status = self.build_target(app, parallel=parallel, target=str('all'), silent=silent)
        if not build_status['result']:
            return build_status
        # Clean Application after build if requested
        if post_clean:
            clean_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not clean_status['result']:
                return clean_status

        return build_status

    def build_bin(self, app, parallel=False, pre_clean=False, post_clean=False):
        # Clean Application before build if requested
        if pre_clean:
            build_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not build_status['result']:
                return build_status

        # Build Application
        build_status = self.build_target(app, parallel=parallel, target=str('bin'))
        if not build_status['result']:
            return build_status
        # Clean Application after build if requested
        if post_clean:
            clean_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not clean_status['result']:
                return clean_status

        return build_status

    def build_hex(self, app, parallel=False, pre_clean=False, post_clean=False):
        # Clean Application before build if requested
        if pre_clean:
            build_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not build_status['result']:
                return build_status

        # Build Application
        build_status = self.build_target(app, parallel=parallel, target=str('hex'))
        if not build_status['result']:
            return build_status
        # Clean Application after build if requested
        if post_clean:
            clean_status = self.build_target(app, parallel=parallel, target=str('clean'))
            if not clean_status['result']:
                return clean_status

        return build_status

    def get_build_size(self, app, parallel=False, silent=False):
        # Build Application
        build_status = self.build_target(app, parallel=parallel, target=str('all'))
        if not build_status['result']:
            return build_status
        with open("elf", "rb") as f:
            elffile = ELFFile(f)
            section_names = list()
            section_size = list()
            for section in elffile.iter_sections():
                section_names.append(section.name)
                section_size.append(section.data_size)
            table = PrettyTable(section_names)
            table.add_row(section_size)
            print(table.get_string())
        return build_status

    def clean(self, app, parallel=False):
        build_status = self.build_target(app, target=str('clean'), parallel=parallel)
        return build_status

    def distclean(self, app, parallel=False):
        build_status = self.build_target(app, target=str('distclean'), parallel=parallel)
        return build_status

    def boardclean(self, app, parallel=False):
        build_status = self.build_target(app, target=str('boardclean'), parallel=parallel)
        return build_status

    def get_makefile_config(self, build_template=None):
        ospclass = osp.OSP()
        build_template["APPL"] = self.buildopts.get("APPL", False)
        build_template["BOARD"] = self.buildopts.get("BOARD", False)
        build_template["BD_VER"] = self.buildopts.get("BD_VER", False)
        build_template["CUR_CORE"] = self.buildopts.get("CUR_CORE", False)
        build_template["TOOLCHAIN"] = self.buildopts.get("TOOLCHAIN", False)
        build_template["OLEVEL"] = self.buildopts.get("OLEVEL", False)
        osp_root = self.buildopts.get("EMBARC_ROOT", False)

        if not all(build_template.values()):
            default_makefile_config = dict()
            _, default_makefile_config = ospclass.get_makefile_config(default_makefile_config)
            if not osp_root:
                osp_root = default_makefile_config.get("EMBARC_ROOT")
            for key, value in build_template.items():
                if not value:
                    build_template[key] = default_makefile_config.get(key, False)
            self.buildopts.update(build_template)

        osp_root, _ = ospclass.check_osp(osp_root)
        self.buildopts["EMBARC_ROOT"] = osp_root
        build_template["EMBARC_ROOT"] = osp_root

        if not all(build_template.values()):
            try:
                returncode, cmd_output = pqueryTemporaryFile(["make", "EMBARC_ROOT=" + str(osp_root), "info"])
                default_build_option = None
                if not returncode and cmd_output:
                    for line in cmd_output:
                        if line.startswith("BUILD_OPTION"):
                            default_build_option = str(line.split(":", 1)[1]).split()
                            break
                        else:
                            pass
                    default_build_option_dict, _ = get_config(default_build_option)
                    for key, value in build_template.items():
                        if not value:
                            build_template[key] = default_build_option_dict[key]
                    self.buildopts.update(build_template)
            except Exception as e:
                print_string("Error: {}".format(e))
                sys.exit(1)

        generate_json(self.buildopts, self.config_file)
        current_build_list = ["%s=%s" % (key, value) for key, value in self.buildopts.items()]
        # self.make_options = " ".join(current_build_list) + self.make_options
        self.make_options = current_build_list
        if self.outdir is not None:
            self.make_options.append('OUT_DIR_ROOT=' + str(self.outdir))
        print_string("Current configuration ")
        table_head = list()
        table_content = list()
        for key, value in build_template.items():
            table_head.append(key)
            table_content.append(value)
        msg = [table_head, [table_content]]
        print_table(msg)
        self.osproot = osp_root
        return build_template

    def get_build_template(self):

        build_template = BUILD_CONFIG_TEMPLATE
        build_template = collections.OrderedDict()
        return build_template
