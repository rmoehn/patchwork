import re
from typing import Any, Optional, List, Set, Collection

import hypothesis.strategies as st
from hypothesis.searchstrategy import SearchStrategy
from hypothesis.stateful import precondition, rule, RuleBasedStateMachine

from patchwork.actions import Reply, Unlock, AskSubquestion, Scratch
from patchwork.context import Context
from patchwork.datastore import Datastore, Address
from patchwork.hypertext import Workspace
from patchwork.scheduling import RootQuestionSession, Scheduler

# We should allow a simple scratch link for AskSubquestion.
# But not if the scratch is empty.
# Also, asking with only a pointer to another sub-question of the same
# context doesn't make sense.

# Strategies ###############################################

# A strategy for generating hypertext without any pointers. So it's not
# really hypertext, but just text.
#
# Notes:
# - [ and ] are for expanded pointers and $ starts a locked pointer. Currently
#   there is no way of escaping them, so avoid them.
# - min_size=1, because AskSubquestion misbehaves with empty questions. See also
#   issue #11.
ht_text: SearchStrategy[str] \
    = st.text(min_size=1).filter(lambda s: re.search(r"[\[\]$]", s) is None)


def expanded_pointer(hypertext_: SearchStrategy[str]) -> SearchStrategy[str]:
    """Turns a strategy generating hypertext into one generating pointers to it.

    An expanded pointer to hypertext "<some hypertext>" has the form "[<some
    hypertext>]".
    """
    return hypertext_.map(lambda ht_: "[{}]".format(ht_))


def join(l: List[str]) -> str:
    return "".join(l)


# Concerning min_size see the comment above ht_text.
def nonempty_hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating nested non-empty hypertext.

    The resulting strategy can generate any non-empty hypertext. Ie. a mix of
    text, unexpanded pointers, and expanded pointers containing hypertext.

    Parameters
    ----------
    pointers
        Pointers that the strategy may put in the resulting hypertext.

    Returns
    -------
    A strategy that generates hypertext.
    """
    protected_pointers = st.sampled_from(pointers).map(lambda p: p + " ")
    leaves = st.lists(ht_text | protected_pointers, min_size=1).map(join)
    return st.recursive(
        leaves,
        lambda subtree: st.lists(subtree | expanded_pointer(subtree),
                                 min_size=1).map(join)
    ).map(lambda s: s.strip()).filter(lambda s: s)


def hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating possibly empty hypertext.

    See also
    --------
    :py:func:`nonempty_hypertext`
    """
    return st.just("") | nonempty_hypertext(pointers)


def question_hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating hypertext that is suited for questions.

    Some hypertexts are not suited for questions. See issues #11 and #15. This
    procedure returns the same strategy as :py:func:`nonempty_hypertext`, except
    that it filters out those unsuitable cases.

    See also
    --------
    :py:func:`nonempty_hypertext`
    """
    return nonempty_hypertext(pointers).filter(lambda s: s[0] != "[")


# Test case ################################################

def locked_pointers(c: Context) -> List[str]:
    return [pointer for pointer, address in c.name_pointers.items()
            if address not in c.unlocked_locations]


class RandomExercise(RuleBasedStateMachine):
    """Bombard patchwork with random questions, replies etc.

    This doesn't contain any assertions, yet, but at least it makes sure that no
    action will cause an exception or infinite loop.
    """
    def __init__(self):
        super(RandomExercise, self).__init__()
        self.db: Optional[Datastore] = None
        self.sess: Optional[RootQuestionSession] = None


    def pointers(self) -> List[str]:
        """Return a list of the pointers available in the current context."""
        c = self.sess.current_context
        names_pointers = c.name_pointers_for_workspace(c.workspace_link, self.db)
        return list(names_pointers.keys())


    def unaskable_pointers(self) -> Collection[str]:
        """Return pointers that by themselves can't be asked as a subquestion.
        """
        c = self.sess.current_context
        ws: Workspace = self.db.dereference(c.workspace_link)

        unaskable_addrs: List[Address] = [ws.question_link]
        if not self.db.dereference(ws.scratchpad_link):
            unaskable_addrs.append(ws.scratchpad_link)
        unaskable_addrs += [sq[0] for sq in ws.subquestions]  # sq[0]: question
        return {c.pointer_names[a] for a in unaskable_addrs}


    # TODO generation: Make sure that sometimes a question that was asked
    # before is asked again, also in ask(), so that the memoizer is exercised.
    # TODO assertion: The root answer is available immediately iff it was in
    # the datastore already.
    @precondition(lambda self: not self.sess)
    @rule(data=st.data(),
          is_reset_db=st.booleans())
    def start_session(self, data: SearchStrategy[Any], is_reset_db: bool):
        if self.db is None or is_reset_db:
            self.db = Datastore()
        self.sess = RootQuestionSession(
                        Scheduler(self.db),
                        question=data.draw(question_hypertext([])))
        if self.sess.root_answer:
            self.sess = None


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def reply(self, data: SearchStrategy[Any]):
        def not_question(p: str) -> bool:
            return not re.match(r"\$q\d+\Z", p)

        self.sess.act(
            Reply(data.draw(hypertext(self.pointers()).filter(not_question))))
        if self.sess.root_answer:
            self.sess = None


    # TODO assertion: Unlocking already unlocked pointers causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def unlock(self, data: SearchStrategy[Any]):
        lps = locked_pointers(self.sess.current_context)
        self.sess.act(
            Unlock(data.draw(st.sampled_from(lps))))


    # TODO assertion: We should only get that value error when re-asking an
    # ancestor's question.
    # TODO assertion: Asking an unaskable causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def ask(self, data: SearchStrategy[Any]):
        up = self.unaskable_pointers()
        question = data.draw(question_hypertext(self.pointers())
                         .filter(lambda q: q not in up))  # Issue #15.
        try:
            self.sess.act(
                AskSubquestion(question))
        except ValueError as e:
            # If it re-asked an ancestor's question...
            # (For now we'll prevent this error only in this primitive way.)
            if "Action resulted in an infinite loop" in str(e):
                pass
            else:
                raise


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def scratch(self, data: SearchStrategy[Any]):
        self.sess.act(
            Scratch(data.draw(hypertext(self.pointers()))))


TestHypothesis = RandomExercise.TestCase
