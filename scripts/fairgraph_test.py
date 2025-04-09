#!/usr/bin/env python3
"""
Testing out accessing information using FairGraph

File: fairgraph_test.py

Copyright 2025 Ankur Sinha
Author: Ankur Sinha <sanjay DOT ankur AT gmail DOT com>
"""

import sys

from fairgraph import KGClient
from fairgraph.openminds.core import Model


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
    models = Model.list(client, size=1)
    print(models)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Takes one compulsory argument: location of file with EBRAINS token.")
        sys.exit(-1)

    print(sys.argv)
    run(sys.argv[1])
