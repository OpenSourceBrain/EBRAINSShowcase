#!/usr/bin/env python3
"""
Testing out accessing information using FairGraph

File: fairgraph_test.py

Copyright 2025 Ankur Sinha
Author: Ankur Sinha <sanjay DOT ankur AT gmail DOT com>
"""

import json
import sys
import typing

from fairgraph import KGClient, KGProxy
from fairgraph.errors import ResolutionFailure
from fairgraph.openminds.core import FileRepository, Model, ModelVersion


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
    models: Model = Model.list(client, size=300)
    id_h = "ID"
    name_h = "Name"
    file_h = "File location"
    print(f"  {id_h:<40}|{name_h:<50}|{file_h:<70}")
    data: dict[str, dict[str, str]] = {}
    data_type: dict[str, int] = {"github": 0, "cscs": 0, "other": 0}
    errors: dict[str, dict[str, str]] = {}
    num_OK = 0
    num_erred = 0
    data_file = "ebrains-models.json"
    error_file = "ebrains-errors.json"

    for m in models:
        m_id = m.id.split(sep="/")[-1]
        m_versions: list[typing.Union[KGProxy, ModelVersion]] = []
        if isinstance(m.versions, list):
            m_versions = m.versions
        else:
            m_versions = [m.versions]

        for v in m_versions:
            v_r: typing.Optional[ModelVersion] = None
            if isinstance(v, KGProxy):
                try:
                    v_r = v.resolve(client)
                except ResolutionFailure:
                    errors[m_id] = {
                        "name": m.name,
                    }
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
                data[m_id] = {"name": m.name, "repository": repository_r.name}
                if "github" in repository_r.name:
                    data_type["github"] += 1
                elif "cscs.ch" in repository_r.name:
                    data_type["cscs"] += 1
                else:
                    data_type["other"] += 1

                num_OK += 1

            except ResolutionFailure:
                print(f"* ERROR: Could not resolve {repository.id}")
                errors[m_id] = {
                    "name": m.name,
                    "reason": "Repository could not be resolved",
                }
                num_erred += 1
                continue

    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

    with open(error_file, "w") as f:
        json.dump(errors, f, indent=4)

    print(f"{num_OK + num_erred} models processed. {num_OK} OK, {num_erred} errors")
    print(f"Data repo types breakdown: {data_type}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Takes one compulsory argument: location of file with EBRAINS token.")
        sys.exit(-1)

    print(sys.argv)
    run(sys.argv[1])
