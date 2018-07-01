from collections import defaultdict, deque
from typing import Any, DefaultDict, Dict, List, Optional, Set, Union

import parsy

from patchwork.hypertext import Workspace
from .datastore import Address, Datastore
from .hypertext import RawHypertext, visit_unlocked_region

link = parsy.regex(r"\$([awq]?[1-9][0-9]*)")
otherstuff = parsy.regex(r"[^\[\$\]]+")

lbrack = parsy.string("[")
rbrack = parsy.string("]")

@parsy.generate
def subnode():
    yield lbrack
    result = yield hypertext
    yield rbrack
    return result

hypertext = (link | subnode | otherstuff).many()

# MyPy can't deal with this yet
# ParsePiece = Union[str, "ParsePiece"]
ParsePiece = Any

def recursively_create_hypertext(
        pieces: List[ParsePiece],
        db: Datastore,
        pointer_link_map: Dict[str, Address]
        ) -> RawHypertext:
    result: List[Union[Address, str]] = []
    for piece in pieces:
        if isinstance(piece, list):
            result.append(recursively_insert_hypertext(piece, db, pointer_link_map))
        else:
            try:
                # This is a link that should be in the map
                result.append(pointer_link_map[link.parse(piece)])
            except parsy.ParseError:
                # This is just a regular string
                result.append(piece)
    return RawHypertext(result)


def recursively_insert_hypertext(
        pieces: List[ParsePiece],
        db: Datastore,
        pointer_link_map: Dict[str, Address]
        ) -> Address:
    result = db.insert(recursively_create_hypertext(pieces, db, pointer_link_map))
    return result


def insert_raw_hypertext(
        content: str,
        db: Datastore,
        pointer_link_map: Dict[str, Address],
        ) -> Address:
    parsed = hypertext.parse(content)
    return recursively_insert_hypertext(parsed, db, pointer_link_map)


def create_raw_hypertext(
        content: str,
        db: Datastore,
        pointer_link_map: Dict[str, Address]
        ) -> RawHypertext:
    parsed = hypertext.parse(content)
    return recursively_create_hypertext(parsed, db, pointer_link_map)


# ## Data representation of link variants

class Link(object):
    # Credits: https://stackoverflow.com/a/2626364/5091738
    def __repr__(self) -> str:
        """Return a string representation of ``self``.

        Example
        -------
        >>> repr(UnlockedLink("$a1", "shrubbery"))
        "UnlockedLink(content='shrubbery', pointer='$a1')"
        """
        return "{}({})".format(
                self.__class__.__name__,
                ", ".join("{}={!r}".format(k, self.__dict__[k])
                          for k in sorted(self.__dict__.keys())))


class LockedLink(Link):
    def __init__(self, pointer):
        self.pointer = pointer

    def __str__(self) -> str:
        return self.pointer


class AnonymousLink(Link):
    def __init__(self, content):
        self.content = content

    def __str__(self) -> str:
        return "[{}]".format(self.content)


class UnlockedLink(Link):
    def __init__(self, pointer, content):
        self.pointer = pointer
        self.content = content

    def __str__(self) -> str:
        return "[{}: {}]".format(self.pointer, self.content)


# ## Extracting links from hypertext

def make_link_data(
        root_link: Address,
        db: Datastore,
        unlocked_locations: Optional[Set[Address]]=None,
        pointer_names: Optional[Dict[Address, str]]=None,
        ) -> Dict[Address, Link]:
    # We need to construct this string in topological order since pointers
    # are substrings of other unlocked pointers. Since everything is immutable
    # once created, we are guaranteed to have a DAG.
    include_counts: DefaultDict[Address, int] = defaultdict(int)

    for link in visit_unlocked_region(root_link, root_link, db, unlocked_locations):
        page = db.dereference(link)
        for visible_link in page.links():
            include_counts[visible_link] += 1

    assert(include_counts[root_link] == 0)

    no_incomings = deque([root_link])
    order: List[Address] = []
    while len(no_incomings) > 0:
        link = no_incomings.popleft()
        order.append(link)
        if unlocked_locations is None or link in unlocked_locations:
            page = db.dereference(link)
            for outgoing_link in page.links():
                include_counts[outgoing_link] -= 1
                if include_counts[outgoing_link] == 0:
                    no_incomings.append(outgoing_link)

    link_texts: Dict[Address, Link] = {}

    if pointer_names is not None:
        for link in reversed(order):
            if link == root_link:
                continue
            if unlocked_locations is not None and link not in unlocked_locations:
                link_texts[link] = LockedLink(pointer_names[link])
            else:
                page = db.dereference(link)
                content = page.to_data(display_map=link_texts) \
                            if isinstance(page, Workspace) \
                            else page.to_str(display_map=link_texts)

                link_texts[link] = UnlockedLink(pointer_names[link],
                                                content)
    else:
        for link in reversed(order):
            page = db.dereference(link)
            link_texts[link] = AnonymousLink(page.to_data(
                    display_map=link_texts))


    return link_texts


def make_link_texts(
        root_link: Address,
        db: Datastore,
        unlocked_locations: Optional[Set[Address]]=None,
        pointer_names: Optional[Dict[Address, str]]=None,
        ) -> Dict[Address, str]:
    links = make_link_data(root_link, db, unlocked_locations, pointer_names)
    return {k: str(v) for k, v in links.items()}
