# Copyright (C) 2018-2023 Jan Malakhovski
#
# This file can be distributed under the terms of Python Software
# Foundation License version 2 (PSF-2.0) as published by Python
# Software Foundation.

"""Exceptions with printable descriptions.
"""

import typing as _t

class CatastrophicFailure(Exception):
    def __init__(self, what : str, *args : _t.Any) -> None:
        super().__init__()
        self.description = what % args

    def show(self) -> str:
        return self.description

    def elaborate(self, what : str, *args : _t.Any) -> None:
        self.description = what % args + ": " + self.description

class Failure(CatastrophicFailure):
    pass
