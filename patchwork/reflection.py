from typing import Tuple, Union

import attr

from .datastore import Address
from .actions import Action
from .context import Context, DryContext


def dry_cut(context: Context) -> DryContext:
    return DryContext(workspace_link=context.workspace_link,
                      unlocked_locations=frozenset(context.unlocked_locations),
                      parent=None)


@attr.s(frozen=True)
class C(object):
    dry_context = attr.ib(type=Address)  # DryContext


@attr.s(frozen=True)
class CS(C):
    source = attr.ib(type=Address)  # A


@attr.s(frozen=True)
class CSR(C):
    source = attr.ib(type=Address)  # A
    result = attr.ib(type=Address)  # A


@attr.s(frozen=True)
class A(object):
    action = attr.ib(type=Address)  # Action


@attr.s(frozen=True)
class ASSO(A):
    start = attr.ib(type=Address)  # C
    succ = attr.ib(type=Address)  # C
    others = attr.ib(type=Tuple[Address])  # C


@attr.s(frozen=True)
class AS(A):
    succ = attr.ib(type=Address)  # C


@attr.s(frozen=True)
class ASO(A):
    start = attr.ib(type=Address)  # C
    others = attr.ib(type=Tuple[Address])  # C
