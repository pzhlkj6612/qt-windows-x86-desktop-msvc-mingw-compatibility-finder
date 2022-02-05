#!/usr/bin/env python3


import argparse
import json
import os
import re
from functools import reduce
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, ResultSet, Tag
from packaging import version

regex_qt_name_matcher = re.compile(
    # qt5_591/
    # qt5_598/
    # qt5_5100/
    # qt5_51210/
    r"^qt\d_(?P<version>\d+)/$")
regex_qt_package_name_msvc_or_mingw_matcher = re.compile(
    # qt.qt5.5100.win64_msvc2015_64
    #  qt .qt5     .5100.win            64 _              msvc                2015  _ 64
    # qt.qt5.5100.win32_mingw53
    #  qt .qt5     .5100.win            32 _             mingw                  53
    # qt.qt5.51210.win64_mingw73
    #  qt .qt5     .51210.win           64 _             mingw                  73
    # qt.591.win64_msvc2015_64
    #  qt          .591 .win            64 _              msvc                2015  _ 64
    r"^qt(\.qt\d)?\.\d+\.win(?P<arch>\d{2})_(?P<name>msvc|mingw)(?P<version>\d{2,4})(_\d+)?"
)
regex_qt_package_version_matcher = re.compile(
    # 5.10.0-0-201712041208
    # 5.12.10-0-202011040843
    # 6.0.0-0-202012051252
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)-\d+-(?P<release_date_time>\d{12})$"
)

str_url_base_windows_x86_desktop_repository = "https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/"

str_update_xml_filename = "Updates.xml"


def get_base_repository_all_qt_links() -> dict:
    response_base_repository = requests.get(
        url=str_url_base_windows_x86_desktop_repository)
    soup = BeautifulSoup(
        markup=response_base_repository.text, features="html.parser")
    all_a_tags = soup.find_all("a")

    dict_all_qt_links = {}

    for a_tag in all_a_tags:
        match_qt_name = regex_qt_name_matcher.match(a_tag.text)
        if match_qt_name:
            str_qt_version = match_qt_name.group("version")
            str_url_xml = reduce(
                urljoin, [str_url_base_windows_x86_desktop_repository, a_tag.text, str_update_xml_filename])
            dict_all_qt_links[str_qt_version] = str_url_xml

    return dict_all_qt_links


def get_current_qt_version_all_packageUpdates(str_current_qt_version_url: str) -> ResultSet:
    response_current_qt_version = requests.get(
        url=str_current_qt_version_url)
    soup = BeautifulSoup(
        markup=response_current_qt_version.text, features="xml")
    return soup.Updates.find_all("PackageUpdate")


def main():

    ##############################################

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--links-file",
        help="The output JSON file storing all Qt links.",
        required=True
    )
    parser.add_argument(
        "--info-file",
        help="The output JSON file storing all Qt info info.",
        required=True
    )
    parser.add_argument(
        "--result-file",
        help="The output Markdown file storing all human-readable Qt version info.",
        required=True
    )

    args_parsed = parser.parse_args()

    str_links_file_path: str = os.path.abspath(args_parsed.links_file)
    str_info_file_path: str = os.path.abspath(args_parsed.info_file)
    str_result_file_path: str = os.path.abspath(args_parsed.result_file)

    list_file_paths = [
        str_links_file_path,
        str_info_file_path,
        str_result_file_path
    ]

    if len(set(list_file_paths)) != 3:
        raise Exception("Don't specify the same files.")

    for str_file_path in list_file_paths:
        if os.path.exists(str_file_path):
            raise FileExistsError(str_file_path)

    ##############################################

    dict_all_qt_links = get_base_repository_all_qt_links()
    print("all_qt_links:")
    print(dict_all_qt_links)

    with open(str_links_file_path, "w", encoding="utf-8") as fp_links:
        json.dump(dict_all_qt_links, fp_links, indent=4)

    # Structure:
    # {
    #     "$qt_ver": {
    #         "$env_name": {
    #             "$env_version": {
    #                 "$env_arch": "$package_name"
    #             },
    #         }
    #     }
    # }
    #
    dict_all_qt_version_info = {}

    for str_ver_no_delimiter in dict_all_qt_links:
        print(str_ver_no_delimiter)
        str_current_qt_version_url = dict_all_qt_links[str_ver_no_delimiter]
        print(str_current_qt_version_url)
        all_packageUpdates = get_current_qt_version_all_packageUpdates(
            str_current_qt_version_url)

        for packageUpdate in all_packageUpdates:
            packageUpdate: Tag = packageUpdate

            str_package_name = packageUpdate.Name.text
            str_package_version = packageUpdate.Version.text

            match_package_name_msvc_or_mingw = regex_qt_package_name_msvc_or_mingw_matcher.match(
                str_package_name)
            if match_package_name_msvc_or_mingw:
                print(str_package_name)

                str_env_name = match_package_name_msvc_or_mingw.group("name")
                str_env_arch = match_package_name_msvc_or_mingw.group("arch")
                str_env_version = match_package_name_msvc_or_mingw.group(
                    "version")

                match_package_version_msvc = regex_qt_package_version_matcher.match(
                    str_package_version)
                if not match_package_version_msvc:
                    raise Exception(
                        "Wrong version number: {}".format(str_package_version))

                str_qt_version = "{}.{}.{}".format(
                    match_package_version_msvc.group("major"),
                    match_package_version_msvc.group("minor"),
                    match_package_version_msvc.group("patch")
                )

                if not str_qt_version in dict_all_qt_version_info:
                    dict_all_qt_version_info[str_qt_version] = {
                        str_env_name: {
                            str_env_version: {
                                str_env_arch: str_package_name
                            }
                        }
                    }
                else:
                    dict_one_qt_version_info: dict = dict_all_qt_version_info[str_qt_version]

                    if not str_env_name in dict_one_qt_version_info:
                        dict_one_qt_version_info[str_env_name] = {
                            str_env_version: {
                                str_env_arch: str_package_name
                            }
                        }
                    else:
                        dict_one_env: dict = dict_one_qt_version_info[str_env_name]

                        if str_env_version not in dict_one_env:
                            dict_one_env[str_env_version] = {
                                str_env_arch: str_package_name
                            }
                        else:
                            dict_one_env_version_arches: dict = dict_one_env[str_env_version]
                            dict_one_env_version_arches[str_env_arch] = str_package_name
                            dict_one_env[str_env_version] = dict_one_env_version_arches

                        dict_one_qt_version_info[str_env_name] = dict_one_env

                    dict_all_qt_version_info[str_qt_version] = dict_one_qt_version_info

    # Python 3.7+
    dict_all_qt_version_info_sorted = {
        str_qt_version: dict_all_qt_version_info[str_qt_version]
        for str_qt_version in sorted(
            list(dict_all_qt_version_info.keys()),
            key=version.parse,
            reverse=True
        )
    }

    with open(str_info_file_path, "w", encoding="utf-8") as fp_json:
        json.dump(dict_all_qt_version_info_sorted, fp_json, indent=4)

    ##############################################

    str_table_header = "| Package name | Dev env | Version | Arch |"
    str_table_alignment = "|:- |:- |:- |:- |"
    str_table_item_template = "| {:32} | {:5} | {:4} | {:6} "

    str_table_str = ""

    for str_qt_version in dict_all_qt_version_info_sorted:

        list_table_content = []
        list_table_content.append("")
        list_table_content.append("## Qt {}".format(str_qt_version))
        list_table_content.append("")
        list_table_content.append(str_table_header)
        list_table_content.append(str_table_alignment)

        for str_env_name in dict_all_qt_version_info_sorted[str_qt_version]:
            for str_env_version in dict_all_qt_version_info_sorted[str_qt_version][str_env_name]:
                for str_env_arch in dict_all_qt_version_info_sorted[str_qt_version][str_env_name][str_env_version]:
                    str_package_name = dict_all_qt_version_info_sorted[str_qt_version][str_env_name][str_env_version][str_env_arch]
                    list_table_content.append(
                        str_table_item_template.format(
                            str_package_name, str_env_name, str_env_version, str_env_arch
                        )
                    )

        list_table_content.append("")
        str_table_str = str_table_str + "\n".join(list_table_content)

    with open(str_result_file_path, "w", encoding="utf-8") as fp_markdown:
        fp_markdown.write(str_table_str)


if __name__ == "__main__":
    main()
