#!/usr/bin/python3
import sys
from distutils.sysconfig import get_python_lib

sys.path.append(get_python_lib())
import os
import json
import xlsxwriter
import subprocess
import re
import termcolor

sys.path.append('./modules/')
os.chdir(os.path.dirname(os.path.realpath(__file__)))

from create_excel_template import *
from main import *

settings=get_settings()
args=parcer()

servers_for_patching = []

# get_file_name
today = datetime.datetime.now()

# counter for chart
need_patching = not_need_patching = error_count = 0

packages_which_require_reboot = ("glibc", "hal", "systemd", "udev")

def write_to_excel_file(content_updates_pkgs, content_all_pkgs, idx, sheet):
    """Function to write content to xlsx-file"""
    global need_patching
    global not_need_patching
    global error_count
    kernel_update = reboot_require = "no"
    format_kernel = format_reboot = format_potential_risky_packages = format['format_green']
    no_potential_risky_packages = "yes"
    column_width=[]
    column_width.append(max(len(key) for key in content_updates_pkgs.keys()))
    column_width.append(max(len(str(value)) for value in content_updates_pkgs.values()))
    column_width.append(max(len(key) for key in content_updates_pkgs.keys()))
    counter = 0
    # avoid the bug #41479 https://github.com/saltstack/salt/issues/41479
    try:
        content_updates_pkgs.pop("retcode")
        content_all_pkgs.pop("retcode")
    except KeyError:
        pass
    for key, value in sorted(content_updates_pkgs.items()):
        if no_potential_risky_packages == "yes":
            for current_bad_package in settings['bad_packages']:
                if str(key).startswith(current_bad_package):
                    no_potential_risky_packages = "no"
                    format_potential_risky_packages = format['format_red']
                    break
        if kernel_update == "no":
            if str(key).startswith("kernel") == True or str(key).startswith("linux-image") == True:
                kernel_update = "yes"
                format_kernel = format['format_red']
                reboot_require = "yes"
                format_reboot = format['format_red']
        sheet.write(counter + 2, 0, key, format['format_border'])
        try:
            sheet.write(counter + 2, 1, content_all_pkgs[key], format['format_border'])
        except KeyError:
            sheet.write(counter + 2, 1, "new packages (will be installed as dependency)", format['format_border'])
        sheet.write(counter + 2, 2, value, format['format_border'])
        counter += 1
    if kernel_update == "no":
        for current_package in packages_which_require_reboot:
            if current_package in content_updates_pkgs.keys():
                reboot_require = "yes"
                format_reboot = format['format_red']
                break
        if reboot_require == "no":
            for current_package in content_updates_pkgs.keys():
                if current_package.find("-firmware-") != -1:
                    reboot_require = "yes"
                    format_reboot = format['format_red']
                    break
    for c in range(3):
        sheet.set_column(c,c,width=column_width[c]+2)
    total_sheet.write(idx + 2, 3, kernel_update, format_kernel)
    total_sheet.write(idx + 2, 4, reboot_require, format_reboot)
    total_sheet.write(idx + 2, 5, no_potential_risky_packages, format_potential_risky_packages)
    if counter > 0:
        need_patching += 1;
        servers_for_patching.append(sheet.get_name())
    else:
        not_need_patching += 1
    write_to_total_sheet(counter, "", sheet, total_sheet, format, idx, 'centos')

def main_function():
    global error_count
    file= open('./server_list.txt', 'r')
    server_list = open('./server_list.txt', 'r').read().rstrip().split('\n')
    file.close()

    print("Starting to collect patching list for servers: " + ','.join(server_list))

    try:
        proc_get_updates = subprocess.Popen("salt -L '" + ','.join(
            server_list) + "' pkg.list_upgrades refresh=True --output=json --static  --hide-timeout",
                                            shell=True, universal_newlines=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
        stdout_get_updates, stderr_get_updates = proc_get_updates.communicate(timeout=300)
        proc_get_all_pkgs = subprocess.Popen(
            "salt -L '" + ','.join(server_list) + "' pkg.list_pkgs --output=json --static  --hide-timeout",
            shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_get_all_pkgs, stderr_get_all_pkgs = proc_get_all_pkgs.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        proc_get_updates.kill()
        proc_get_all_pkgs.kill()
        print("There are problem with salt! ")
        os._exit(1)


    # avoid the bug #40311 https://github.com/saltstack/salt/issues/40311
    stdout_get_updates = re.sub("Minion .* did not respond. No job will be sent.", "", stdout_get_updates)
    stdout_get_updates = re.sub("No minions matched the target. No command was sent, no jid was assigned.", "",
                                stdout_get_updates)
    stdout_get_updates == re.sub("minion .* was already deleted from tracker, probably a duplicate key", "",
                                 stdout_get_updates)
    proc_out_get_updates_json = json.loads(stdout_get_updates)
    stdout_get_all_pkgs = re.sub("Minion .* did not respond. No job will be sent.", "", stdout_get_all_pkgs)
    stdout_get_all_pkgs = re.sub("No minions matched the target. No command was sent, no jid was assigned.", "",
                                 stdout_get_all_pkgs)
    stdout_get_all_pkgs = re.sub("minion .* was already deleted from tracker, probably a duplicate key", "",
                                 stdout_get_all_pkgs)
    proc_out_get_all_pkgs_json = json.loads(stdout_get_all_pkgs)

    print('Starting to create xlsx-file...')
    error_list_from_xlsx = []

    for idx, current_server in enumerate(server_list):
        try:
            sheet = xls_file.add_worksheet(current_server)
            write_to_excel_file(proc_out_get_updates_json[current_server], proc_out_get_all_pkgs_json[current_server], idx, sheet)
        except KeyError:
            error_list_from_xlsx.append(current_server)
            write_to_total_sheet("unknown error", "error", sheet, total_sheet, format, idx, 'centos')
            sheet.set_column(0, 0, width=17)
            error_count+=1
        except Exception as e:
            error_list_from_xlsx.append(current_server)
            termcolor.cprint(
                'Error occured during creation the sheet %s. Perhaps you have two or more same servers in server_list.txt file' % current_server,
                color='red', on_color='on_white')
    if error_list_from_xlsx:
        termcolor.cprint("There are problem with following servers:\n" + ', '.join(error_list_from_xlsx), color='red',
                         on_color='on_white')
    add_chart(need_patching, not_need_patching, error_count, xls_file, total_sheet, format)
    xls_file.close()
    perform_additional_actions(args, today, 'centos', xlsx_name, settings, servers_for_patching)

# get server list and raise main function
print("Hello! Nice to meet you!")
termcolor.cprint(
    ", // ,,/ ,.// ,/ ,// / /, // ,/, /, // ,/,\n/, // ,/,_|_// ,/ ,, ,/, // ,/ /, //, /,/\n /, /,.-'   '-. ,// ////, // ,/,/, // ///\n, ,/,/         \ // ,,///, // ,/,/, // ,\n,/ , ^^^^^|^^^^^ ,// ///  /,,/,/, ///, //\n / //     |  O    , // ,/, //, ///, // ,/\n,/ ,,     J\/|\_ |+'(` , |) ^ ||\|||\|/` |\n /,/         |   || ,)// |\/-\|| ||| |\] .\n/ /,,       /|    . ,  ///, . /, // ,//, /\n, / /,/     \ \    ). //, ,( ,/,/, // ,/,",
    color='blue', on_color='on_grey')
print("Starting to collect of all patches...")
xlsx_name = 'Linix_list_of_updates_' + str(today.strftime("%B_%Y")) + "_Centos.xlsx"
xls_file = xlsxwriter.Workbook(xlsx_name)
format=create_formats(xls_file)
total_sheet=create_total_sheet(xls_file, format)
create_xlsx_legend(total_sheet, format)
main_function()
