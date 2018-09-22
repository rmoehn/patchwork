from typing import Tuple, Union

import attr

from .actions import Action
from .context import DryContext
from .hypertext import Hypertext


@attr.s(frozen=True)
class AS(object):
    act = attr.ib(Action)
    succ = attr.ib(type=DryContext)


@attr.s(frozen=True)
class SASO(object):
    start = attr.ib(type=DryContext)
    act = attr.ib(type=Action)
    succ = attr.ib(type=DryContext)
    other = attr.ib(type=Tuple[DryContext])


@attr.s(frozen=True)
class S(object):
    # Would be better if we had a variant type.
    source = attr.ib(type=Union[AS, SASO])


@attr.s(frozen=True)
class S(object):
    source = attr.ib(type=Union[AS, SASO])
    result = attr.ib(type=SASO)


# Hm, do we want to store actual objects at all? Or addresses?
# How do we traverse? With every context we have to store the references.
# Or how? Hm.

# My graphs on paper only have context and action nodes. If we store
# bidirectional links between contexts and actions, we can derive the rest.


#RAction = Union["ASSO", "ASO", "AS"]
#RContext =

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
