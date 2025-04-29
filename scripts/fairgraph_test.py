#!/usr/bin/env python3
"""
Testing out accessing information using FairGraph

File: fairgraph_test.py

Copyright 2025 Ankur Sinha
Author: Ankur Sinha <sanjay DOT ankur AT gmail DOT com>
"""

import json
import logging
import sys
import typing

import requests
from fairgraph import KGClient, KGProxy
from fairgraph.errors import ResolutionFailure
from fairgraph.openminds.core import FileRepository, Model, ModelVersion

logging.basicConfig()
logger = logging.getLogger("fairgraph_test")
logger.setLevel(logging.DEBUG)


def get_ebrains_data_proxy_file_list(url: str) -> list[str]:
    """Get the list of files from an ebrains data proxy URL.

    The complete url will be of this form:

    .. code-block::

        https://data-proxy.ebrains.eu/api/v1/buckets/m-0ffae3c2-443c-44fd-919f-70a4b01506a4?prefix=CA1_pyr_mpg150211_A_idA_080220241322/

    The API documentation is here:
    https://data-proxy.ebrains.eu/api/docs

    This URL returns a JSON response with all the objects listed.
    So we can get the file list from there. To get the download URL, we need
    this end point for each object in the list:

    .. code-block::

        /v1/buckets/{bucket_name}/{object_name}

    :param url: url of repository
    :returns: dict of files and their download URLs

    """
    file_list: dict[str, str] = {}
    top_level_url: str = url.split("?prefix=")[0]

    r = requests.get(url)
    if r.status_code == 200:
        logger.debug("data-proxy: response is")
        logger.debug(r)

        json_r = r.json()
        object_list = json_r["objects"]
        for anobject in object_list:
            object_url = top_level_url + "/" + anobject["name"]
            file_list[anobject["name"]] = object_url

    else:
        logger.error(f"Something went wrong: {r.response_code}")

    if len(file_list.items()) == 0:
        logger.warn("No files found for this: check kg.ebrains.eu to verify")

    return file_list


def get_cscs_file_list(url: str) -> dict[str, str]:
    """Get the list of files from a CSCS repository URL.

    The complete url will be of this form:

    .. code-block:

        https://object.cscs.ch/v1/AUTH_c0a333ecf7c045809321ce9d9ecdfdea/hippocampus_optimization/rat/CA1/v4.0.5/optimizations_Python3/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006.zip?use_cell=cell_seed3_0.hoc&bluenaas=true

    To get the file list, we only need the top level:

    .. code-block::

        https://object.cscs.ch/v1/AUTH_c0a333ecf7c045809321ce9d9ecdfdea/hippocampus_optimization

    We then need to limit the file list to the bits we want, because the top
    level container contains all the files and all the versions:

    .. code-block::

        rat/CA1/v4.0.5/optimizations_Python3/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006

    Note that even if the url is wrong (eg, in the shown example, the file list
    does not include a folder called `optimizations_Python3` at all), the cscs
    server still returns a zip. However, manually checking search.kg.ebrains.eu
    shows that the corresponding entry does not have a file list. It simply
    says "no files available".

    Also note that the url may include a `prefix=` parameter which specifies
    the file directory structure.

    Most of these directories also include a zipped version. For the moment, we
    include this in the file list.

    :param url: url of repository
    :returns: dict of files and their download URLs

    """
    file_list: dict[str, str] = {}
    file_list_url: str = ""
    file_list_string: str = ""

    logger.info(f"Getting file list for {url}")
    if ".zip?" in url:
        url_portions: list[str] = url.split(".zip")[0].split("/")
        file_list_url = "/".join(url_portions[:6])
        logger.info(f"URL for file list: {file_list_url}")
        file_list_string = "/".join(url_portions[6:])
    # assume it's with prefix
    elif "?prefix=" in url:
        file_list_url = url.split("?prefix=")[0]
        file_list_string = url.split("?prefix=")[1]
    else:
        logger.error(f"New cscs url format: {url}")
        return file_list

    r = requests.get(file_list_url)
    if r.status_code == 200:
        logger.debug("CSCS: response is")
        logger.debug(r)

        for line in r.text.split():
            logger.debug(f"CSCS: looking at line: {line}")
            if (
                line.startswith(file_list_string)
                and not line.endswith("/")
                and line != file_list_string
            ):
                file_list[line] = file_list_url + "/" + line
    else:
        logger.error(f"Something went wrong: {r.response_code}")

    if len(file_list) == 0:
        logger.warn("No files found for this: check kg.ebrains.eu to verify")
    return file_list


def run(tokenfile: str):
    """Main runner function

    :param tokenfile: location of file holding the token on a single line
    :type tokenfile: str
    """
    token = None
    with open(tokenfile, "r") as f:
        token = f.readline().strip()

    assert token
    print("Token is: ")
    print(f"{token}")

    client = KGClient(token=token, host="core.kg.ebrains.eu")

    # web interface says there are 266 models
    models: list[Model] = Model.list(client, size=300)
    id_h = "ID"
    name_h = "Name"
    file_h = "File location"
    print(f"  {id_h:<40}|{name_h:<50}|{file_h:<70}")
    data: dict[str, dict[str, typing.Union[str, list[str]]]] = {}
    data_type: dict[str, int] = {
        "github": 0,
        "cscs": 0,
        "modeldb": 0,
        "data-proxy": 0,
        "other": 0,
    }
    errors: dict[str, dict[str, str]] = {}
    num_OK = 0
    num_erred = 0
    data_file = "ebrains-models.json"
    error_file = "ebrains-errors.json"

    for m in models:
        m_id = m.id.split(sep="/")[-1]
        m_versions: list[typing.Union[KGProxy, ModelVersion]] = []

        keywords: list[str] = []
        files: dict[str, str] = {}
        if m.study_targets:
            if isinstance(m.study_targets, KGProxy):
                keyws = m.study_targets.resolve(client)
            else:
                keyws = m.study_targets

            if isinstance(keyws, list):
                for k in keyws:
                    if isinstance(k, KGProxy):
                        keywords.append(k.resolve(client).name)
                    else:
                        keywords.append(k.name)
            else:
                if isinstance(keyws, KGProxy):
                    keywords.append(keyws.resolve().name)
                else:
                    keywords.append(keyws.name)

        if m.abstraction_level:
            if isinstance(m.abstraction_level, KGProxy):
                abs_l = m.abstraction_level.resolve(client)
            else:
                abs_l = m.abstraction_level
            keywords.append(abs_l.name)

        description = f"{m.description}"

        if isinstance(m.versions, list):
            m_versions = m.versions
        else:
            m_versions = [m.versions]

        for v in m_versions:
            # each version will have a unique description
            v_description = f"{description}"

            v_r: typing.Optional[ModelVersion] = None
            if isinstance(v, KGProxy):
                try:
                    v_r = v.resolve(client)
                except ResolutionFailure:
                    print(f"ERROR: Could not resolve {v.id}")
                    errors[m_id] = {
                        "name": m.name,
                        "reason": "ModelVersion could not be resolved",
                    }
                    num_erred += 1
                    continue
            else:
                v_r = v
            repository: FileRepository = v_r.repository
            if not repository:
                print(f"ERROR: No repository attached to {v.id}")
                errors[m_id] = {"name": m.name, "reason": "no repository attached"}
                num_erred += 1
                continue
            try:
                repository_r = repository.resolve(client)
                print(f"* {m_id:<40}|{m.name[:45]:<50}|{repository_r.name:<70}")

                v_description += (
                    f"\n{v_r.version_innovation}" if v_r.version_innovation else ""
                )
                data[m_id] = {
                    "name": m.name,
                    "repository": repository_r.name,
                    "description": v_description,
                    "version": v_r.version_identifier,
                    "keywords": keywords,
                }
                if "github" in repository_r.name:
                    data_type["github"] += 1
                    files = ["NA: get from GitHub adapter"]
                    data[m_id]["files"] = files
                elif "cscs.ch" in repository_r.name:
                    data_type["cscs"] += 1
                    files = get_cscs_file_list(repository_r.name)
                elif "modeldb" in repository_r.name or "yale" in repository_r.name:
                    data_type["modeldb"] += 1
                    files = [
                        "NA: get from corresponding GitHub repo using GitHub adapter"
                    ]
                elif "data-proxy.ebrains.eu" in repository_r.name:
                    data_type["data-proxy"] += 1
                    files = get_ebrains_data_proxy_file_list(repository_r.name)
                else:
                    data_type["other"] += 1
                    files = ["TODO: handle other special cases"]

                data[m_id]["files"] = files
                num_OK += 1

            except ResolutionFailure:
                print(f"* ERROR: Could not resolve {repository.id}")
                errors[m_id] = {
                    "name": m.name,
                    "reason": "Repository could not be resolved",
                }
                num_erred += 1
                continue

    print(data)
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

    with open(error_file, "w") as f:
        json.dump(errors, f, indent=4)

    print(f"{num_OK + num_erred} models processed. {num_OK} OK, {num_erred} errors")
    print(f"Data repo types breakdown: {data_type}")


if __name__ == "__main__":
    # fl = get_cscs_file_list("https://object.cscs.ch/v1/AUTH_c0a333ecf7c045809321ce9d9ecdfdea/hippocampus_optimization/rat/CA1/v4.0.5/optimizations_Python3/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006/CA1_pyr_cACpyr_mpg141208_B_idA_20190328144006.zip?use_cell=cell_seed3_0.hoc&bluenaas=true")
    # print(fl)
    # sys.exit(0)

    if len(sys.argv) != 2:
        print("Takes one compulsory argument: location of file with EBRAINS token.")
        sys.exit(-1)

    print(sys.argv)
    run(sys.argv[1])
