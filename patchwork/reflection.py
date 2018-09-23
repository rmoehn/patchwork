from typing import Tuple, Union

import attr

from .actions import Action
from .context import DryContext


@attr.s(frozen=True)
class C(object):
    dry_context = attr.ib(type=DryContext)


@attr.s(frozen=True)
class CS(C):
    source = attr.ib(type="A")


@attr.s(frozen=True)
class CSR(C):
    source = attr.ib(type="A")
    result = attr.ib(type="A")


@attr.s(frozen=True)
class A(object):
    action = attr.ib(type=Action)


@attr.s(frozen=True)
class ASSO(A):
    start = attr.ib(type="C")
    succ = attr.ib(type="C")
    others = attr.ib(type=Tuple["C"])


@attr.s(frozen=True)
class AS(A):
    succ = attr.ib(type="C")


@attr.s(frozen=True)
class ASO(A):
    start = attr.ib(type="C")
    others = attr.ib(type=Tuple["C"])
