#!/usr/bin/python
from __future__ import print_function, unicode_literals
import os
import re
from distutils.spawn import find_executable
from bs4 import BeautifulSoup
import serial
import subprocess
import threading
from dateutil.parser import parse
import argparse
from embarc_tools.utils import delete_dir_files, processcall, getcwd, cd, mkdir
from embarc_tools.exporter import Exporter


def nt_posix_path(path):
    path = os.path.abspath(path)
    if os.path.exists(path):
        return path.replace("\\", "/")
    else:
        print("{} doesn't exists".format(path))


def generate_gcov_report(root, app_path, obj_path, output):
    gcov_cmd = None
    if find_executable("arc-elf32-gcov"):
        gcov_cmd = "arc-elf32-gcov"
        cmd = ["gcovr", "--gcov-executable", gcov_cmd]
        cmd.extend(["-r", root])
        cmd.extend(["--object-directory", obj_path])
        cmd.extend(["--html", "--html-details",
                    "-o", output])
        processcall(cmd, stderr=subprocess.PIPE)
    else:
        print("Please install arc-elf32-gcov")


def generate_gdb_command(root, board, build_path):
    openocd = None
    object_file = None
    gnu_exec_path = find_executable("arc-elf32-gcc")
    openocd_cfg = None
    if gnu_exec_path and board != "nsim":
        gnu_root = os.path.dirname(gnu_exec_path)
        openocd = os.path.join(
            os.path.dirname(gnu_root),
            "share",
            "openocd",
            "scripts"
        )
        if board == "iotdk" or board == "emsdp":
            board_root = os.path.join(
                root,
                "board",
                board
            )
            board_cfg = "snps_" + board + ".cfg"
            for cur_root, _, files in os.walk(board_root):
                if board_cfg in files:
                    openocd_cfg = os.path.join(
                        cur_root,
                        board_cfg
                    )
        else:
            if board == "emsk":
                board_cfg = "snps_em_sk.cfg"
            elif board == "axs":
                board_cfg = "snps_axs103_hs36.cfg"
            elif board == "hsdk":
                board_cfg = "snps_hsdk.cfg"
            else:
                board_cfg = None
            if board_cfg:
                cfg_root = os.path.join(
                    openocd,
                    "board"
                )
                if board_cfg in cfg_root:
                    openocd_cfg = os.path.join(
                        cfg_root,
                        board_cfg
                    )
    for cur_root, _, files in os.walk(build_path):
        for file in files:
            if os.path.splitext(file)[-1] == ".elf":
                object_file = os.path.join(
                    cur_root,
                    file
                )
                break

    exporter = Exporter("coverage")
    config = {"board": board}
    config["object_file"] = object_file.replace("\\", "/")
    if board != "nsim":
        config = {"openocd": openocd.replace("\\", "/")}
        config = {"openocd_cfg": openocd_cfg.replace("\\", "/")}

    exporter.gen_file_jinja(
        "coverage.gdb.tmpl",
        config,
        "coverage.gdb",
        getcwd()
    )


def get_gcov_data(report):
    data = list()
    with open(report, "r") as f:
        content = f.read()
        content_bf = BeautifulSoup(content, "html.parser")
        items = content_bf.find_all("table")
        summary_bf = BeautifulSoup(str(items[0]), "html.parser")
        td_items = summary_bf.find_all("td")
        for td_item in td_items:
            if td_item.get("class"):
                key = td_item.get("class")[0]
                value = td_item.text
                item = {key: value}
                data.append(item)
        detail = list()
        detail_report_files = list()
        center_content = content_bf.find_all("center")[0]
        tr_contents = center_content.findAll('tr')
        for tr in tr_contents:
            if "href=" in str(tr):
                href = tr.findAll('a', href=True)[0]
                html_name = href['href']
                href['href'] = "#" + html_name
                detail.append(str(tr).replace(u'\xa0', u''))
                with open(os.path.join("coverage", html_name), "r") as key_f:
                    detail_content = key_f.read()
                    detail_bf = BeautifulSoup(detail_content, "html.parser")
                    cov_detail = detail_bf.findAll('table', attrs={'cellspacing': '0', 'cellpadding': '1'})[0]
                    if cov_detail:
                        # Some characters in gmsl cannot be parsed
                        detail_report_files.append(
                            {"name": html_name, "detail": str(cov_detail).replace(u'\xa0', u'')}
                        )
        data.append({"detail": detail})
        data.append({"files": detail_report_files})
    return data


def generate_sum_report(root, app_path, obj_path):
    result = dict()
    headName = None
    try:
        mkdir("coverage")
        with cd("coverage"):
            generate_gcov_report(root, app_path, obj_path, "coverage_sum.html")
            generate_gcov_report(app_path, app_path, obj_path, "main.html")
        osp_data = get_gcov_data("coverage/coverage_sum.html")
        main_data = get_gcov_data("coverage/main.html")

        for i in range(len(osp_data)):
            osp_data_item = osp_data[i]
            main_data_item = main_data[i]
            for key, value in osp_data_item.items():
                if key == "detail":
                    result["detail"] = value + main_data_item[key]
                if key == "files":
                    result["files"] = value + main_data_item[key]
                if "headerName" in key:
                    headName = value
                    continue
                if headName in ["Date:", "Lines:", "Branches:"]:
                    if "Date" in headName and \
                            result.get("Date", None) is None:
                        if "headerValue" in key:
                            try:
                                parse(value)
                                result["Date"] = value
                                continue
                            except Exception as e:
                                print("Sting is not a date {}".format(e))
                    if "Lines" in headName and \
                            result.get("LineExec", None) is None:
                        if "headerTableEntry" in key:
                            result["LineExec"] = int(value) + int(main_data_item[key])
                            continue
                    if "Lines" in headName and \
                            result.get("LineTotal", None) is None:
                        if "headerTableEntry" in key:
                            result["LineTotal"] = int(value) + int(main_data_item[key])
                            result["LineCoverage"] = float(result["LineExec"] * 100 / result["LineTotal"])
                            continue
                    if "Branches" in headName and \
                            result.get("BrancheExec", None) is None:
                        if "headerTableEntry" in key:
                            result["BrancheExec"] = int(value) + int(main_data_item[key])
                            continue
                    if "Branches" in headName and \
                            result.get("BrancheTotal", None) is None:
                        if "headerTableEntry" in key:
                            result["BrancheTotal"] = int(value) + int(main_data_item[key])
                            result["BrancheCoverage"] = float(result["BrancheExec"] * 100 / result["BrancheTotal"])
                            continue
                else:
                    continue
        exporter = Exporter("coverage")
        exporter.gen_file_jinja(
            "gcov.html.tmpl",
            result,
            "gcov.html",
            getcwd(),
        )
    finally:
        delete_dir_files("coverage", dir=True)


def monitor_serial(ser, pro, output_file):
    for line in iter(proc.stdout.readline, b''):
        line_str = line.decode('utf-8')
        print(line_str, end="")
        if ".elf" in line_str:
            break
    print("Start monitor serial ...")
    log_out_fp = open(output_file, "wt")
    flag = 0
    serial_line = None
    while ser.isOpen():
        try:
            serial_line = ser.readline()
        except TypeError:
            pass
        except serial.serialutil.SerialException:
            ser.close()
            break
        sl = serial_line.decode('utf-8', 'ignore')
        if sl and flag:
            log_out_fp.write(sl)
            log_out_fp.flush()
        else:
            print(sl, end="")
        if "embARC unit test end" in sl:
            flag = 1
            print("[embARC] Dump coverage data to file ...")
        if "GCOV_COVERAGE_DUMP_END" in sl:
            ser.close()
            break


def output_reader(proc, output_file):
    log_out_fp = open(output_file, "wt")
    flag = 0
    for line in iter(proc.stdout.readline, b''):
        line_str = line.decode('utf-8')
        if flag and line_str:
            log_out_fp.write(line_str)
            log_out_fp.flush()
        else:
            print(line_str, end="")
        if "embARC unit test end" in line_str:
            flag = 1
            print("[embARC] Dump coverage data to file ...")
        if "GCOV_COVERAGE_DUMP_END" in line_str:
            try:
                proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                proc.terminate()
                break
    log_out_fp.close()


def retrieve_data(input_file):
    extracted_coverage_info = {}
    capture_data = False
    reached_end = False
    with open(input_file, 'r') as fp:
        for line in fp.readlines():
            if re.search("GCOV_COVERAGE_DUMP_START", line):
                capture_data = True
                continue
            if re.search("GCOV_COVERAGE_DUMP_END", line):
                reached_end = True
                break
            # Loop until the coverage data is found.
            if not capture_data:
                continue
            if "<" in line:
                # Remove the leading delimiter "*"
                file_name = line.split("<")[0][1:]
                # Remove the trailing new line char
                hex_dump = line.split("<")[1][:-1]
                extracted_coverage_info.update({file_name: hex_dump})

    if not reached_end:
        print("incomplete data captured from %s" % input_file)
    return extracted_coverage_info


def create_gcda_files(extracted_coverage_info):
    print("[embARC] Generating gcda files")
    for filename, hexdump_val in extracted_coverage_info.items():
        # if kobject_hash is given for coverage gcovr fails
        # hence skipping it problem only in gcovr v4.1
        if "kobject_hash" in filename:
            filename = filename[:-4] + "gcno"
            try:
                os.remove(filename)
            except Exception:
                pass
            continue

        with open(filename, 'wb') as fp:
            fp.write(bytes.fromhex(hexdump_val))


def run(app_path, buildopts, outdir=None, serial_device=None):
    command = None
    target_file = os.path.join(app_path, "coverage.log")
    relative_object_directory = "obj_{}_{}/{}_{}".format(
        buildopts["BOARD"],
        buildopts["BD_VER"],
        buildopts["TOOLCHAIN"],
        buildopts["CUR_CORE"]
    )
    object_directory = os.path.join(
        app_path,
        relative_object_directory
    ).replace("\\", "/")
    with cd(app_path):
        if outdir is None:
            outdir = app_path
        print("[embARC] Start to run ...")
        command = ["make",
                   "EMBARC_ROOT=" + buildopts["EMBARC_ROOT"],
                   "BOARD=" + buildopts["BOARD"],
                   "BD_VER=" + buildopts["BD_VER"],
                   "CUR_CORE=" + buildopts["CUR_CORE"],
                   "TOOLCHAIN=" + buildopts["TOOLCHAIN"],
                   "EN_COVERAGE=1",
                   "run"
                   ]
        if buildopts["BOARD"] == "nsim":
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=app_path
            ) as proc:
                t = threading.Thread(
                    target=output_reader,
                    args=(proc, target_file)
                )
                t.start()
                t.join(1000)
                if t.is_alive():
                    proc.terminate()
                    t.join()
                proc.terminate()
                proc.wait()
                proc.returncode
        else:
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                ser = serial.Serial(
                    serial_device,
                    baudrate=115200,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=0.5
                )
                ser.flush()
                t = threading.Thread(
                    target=monitor_serial,
                    daemon=True,
                    args=(ser, proc, target_file)
                )
                t.start()
                t.join(1000)
                if t.is_alive():
                    proc.terminate()
                    t.join()
                proc.terminate()
                proc.wait()
                proc.returncode
        extracted_coverage_info = retrieve_data(target_file)
        create_gcda_files(extracted_coverage_info)
        generate_sum_report(
            buildopts["EMBARC_ROOT"],
            app_path,
            object_directory
        )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Before run this script, you must build the project.\n \
            Please set OLEVEL=O0.print.\n \
            This function will be added to embARC CLI later",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--embarc-root",
        required=True, help="Specify embARC_osp directory")
    parser.add_argument(
        "--app-path", default=getcwd(),
        required=True, help="Specify the root path of project")
    parser.add_argument(
        "-O", "--outdir", default=getcwd(),
        help="Output directory for makefile, source code and elf.", metavar='')
    parser.add_argument(
        "-b", "--board", help="choose board", default="nsim", metavar='')
    parser.add_argument(
        "--bd-ver", help="choose board version", metavar='')
    parser.add_argument(
        "--cur-core", help="choose core", metavar='')
    parser.add_argument(
        "--toolchain",
        choices=["mw", "gnu"], help="choose toolchain", metavar='')
    parser.add_argument(
        "--device-serial",
        help="Serial device for accessing the board (e.g., /dev/ttyACM0)",
        metavar='')
    return parser.parse_args()


def main():
    global options
    options = parse_arguments()
    options.app_path = nt_posix_path(
        options.app_path
    )
    options.embarc_root = nt_posix_path(
        options.embarc_root
    )
    buildopts = dict()
    buildopts["BOARD"] = options.board
    buildopts["BD_VER"] = options.bd_ver
    buildopts["CUR_CORE"] = options.cur_core
    buildopts["TOOLCHAIN"] = options.toolchain
    buildopts["OLEVEL"] = "O0"
    buildopts["EMBARC_ROOT"] = options.embarc_root
    run(options.app_path, buildopts, options.outdir, options.device_serial)


if __name__ == "__main__":
    main()
