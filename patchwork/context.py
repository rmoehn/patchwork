from collections import defaultdict, deque
from textwrap import indent
from typing import Any, Dict, Optional, Set, Tuple

from .datastore import Address, Datastore
from .hypertext import Workspace, visit_unlocked_region
from .text_manipulation import make_link_data

class Context(object):
    def __init__(
            self,
            workspace_link: Address,
            db: Datastore,
            unlocked_locations: Optional[Set[Address]]=None,
            parent: Optional["Context"]=None,
            ) -> None:

        # Unlocked locations should be in terms of the passed in workspace_link.

        self.workspace_link = workspace_link
        workspace = db.dereference(workspace_link)
        if unlocked_locations is not None:
            self.unlocked_locations = unlocked_locations
            self.unlocked_locations.add(self.workspace_link)
        else:
            # All of the things that are visible in a context with no explicit unlocks.
            self.unlocked_locations = set(
                    [workspace_link, workspace.question_link, workspace.scratchpad_link] +
                    [q for q, a, w in workspace.subquestions] +
                    ([workspace.predecessor_link] if workspace.predecessor_link else []))

        self.pointer_names, self.name_pointers = self._name_pointers(self.workspace_link, db)
        self.display = self.to_str(db)
        self.parent = parent

    def _name_pointers(
            self,
            workspace_link: Address,
            db: Datastore,
            ) -> Tuple[Dict[Address, str], Dict[str, Address]]:
        pointers: Dict[Address, str] = {}
        backward_pointers: Dict[str, Address] = {}

        def assign(link, string):
            pointers[link] = string
            backward_pointers[string] = link

        workspace_root = db.dereference(workspace_link)
        for i, subquestion in reversed(list(enumerate(workspace_root.subquestions, start=1))):
            # Pyre doesn't like tuple destructuring in loops apparently.
            q, a, w = subquestion
            assign(q, "$q{}".format(i))
            assign(a, "$a{}".format(i))
            assign(w, "$w{}".format(i))

        count = 0
        for your_link in visit_unlocked_region(self.workspace_link, workspace_link, db, self.unlocked_locations):
            your_page = db.dereference(your_link)
            for visible_link in your_page.links():
                if visible_link not in pointers:
                    count += 1
                    assign(visible_link, "${}".format(count))

        return pointers, backward_pointers

    def unlocked_locations_from_workspace(
            self,
            workspace_link: Address,
            db: Datastore,
            ) -> Set[Address]:
        result = set(visit_unlocked_region(self.workspace_link, workspace_link, db, self.unlocked_locations))
        return result

    def name_pointers_for_workspace(
            self,
            workspace_link: Address,
            db: Datastore
            ) -> Dict[str, Address]:
        return self._name_pointers(workspace_link, db)[1]


    def to_data(self, db: Datastore) -> Dict[str, Any]:
        link_data = make_link_data(self.workspace_link, db, self.unlocked_locations, self.pointer_names)
        workspace: Workspace = db.dereference(self.workspace_link)

        return {'predecessor':  link_data.get(workspace.predecessor_link),
                'question':     link_data[workspace.question_link],
                'scratchpad':   link_data[workspace.scratchpad_link],
                'subquestions': [{'question':    link_data[q],
                                  'answer':      link_data[a],
                                  'workspace':   link_data[w]}
                                 for q, a, w in workspace.subquestions]}

    def to_str(self, db: Datastore) -> str:
        CONTEXT_FMT = "{predecessor}Question: {question}\nScratchpad: {scratchpad}\nSubquestions:\n{subquestions}\n"
        cdata = self.to_data(db)

        subquestions_str = "\n".join([
            "{}.\n{}\n{}\n{}".format(i,
                                     indent(str(sq['question']), "  "),
                                     indent(str(sq['answer']), "  "),
                                     indent(str(sq['workspace']), "  "))
            for i, sq in enumerate(cdata['subquestions'], start=1)
        ])

        predecessor_str = "Predecessor: {} \n".format(cdata['predecessor']) \
                                if cdata['predecessor'] \
                                else ""

        return CONTEXT_FMT.format(
                predecessor=predecessor_str,
                question=cdata['question'],
                scratchpad=cdata['scratchpad'],
                subquestions=subquestions_str)


    def is_own_ancestor(self, db: Datastore) -> bool:
        initial_workspace = db.canonicalize(self.workspace_link)
        context: Optional[Context] = self.parent
        while context is not None:
            if context == self and db.canonicalize(context.workspace_link) == initial_workspace:
                return True
            context = context.parent
        return False

    def is_blocking(self, db: Datastore) -> bool:
        """Return whether anyone is waiting for an answer from this context."""
        return db.has_promisees(
                    db.dereference(self.workspace_link).answer_promise)


    def __str__(self) -> str:
        return self.display

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if type(other) is not Context:
            return False
        return str(other) == str(self)


