"""Property-based test for Patchwork.

Main class: :py:class:`PatchworkStateMachine`

Also defines :py:class:`TestRandomly`, which unit testing tools can detect.
"""

import logging
import re
import sys
from typing import Any, List, Optional

import hypothesis.strategies as st
from hypothesis.searchstrategy import SearchStrategy
from hypothesis.stateful import RuleBasedStateMachine, precondition, rule

from patchwork.actions import Action, AskSubquestion, Reply, Scratch, Unlock
from patchwork.context import Context
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler
from tests import killable_thread

logging.basicConfig(level=logging.INFO)


# Strategies ###############################################

# A strategy for generating hypertext without any pointers, ie. just text.
#
# Notes:
# - [ and ] are for expanded pointers and $ starts a locked pointer. Currently
#   there is no way of escaping them, so filter them out.
# - min_size=1, because if we allow empty arguments to actions, infinite
#   loops become more likely, which slows down test execution.
ht_text = st.text(min_size=1).filter(lambda t: re.search(r"[\[\]$]", t) is None)


def expanded_pointer(hypertext_: SearchStrategy[str]) -> SearchStrategy[str]:
    """Turns a strategy generating hypertext into one generating pointers to it.

    An expanded pointer to hypertext "<some hypertext>" has the form "[<some
    hypertext>]".
    """
    return hypertext_.map(lambda ht_: "[{}]".format(ht_))


def join(l: List[str]) -> str:
    return "".join(l)


def hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating nested hypertext.

    The resulting strategy can generate any hypertext. Ie. a mix of text,
    unexpanded pointers, and expanded pointers containing hypertext. The
    resulting string won't have whitespace at either end in order to be
    consistent with command-line Patchwork, which strips inputs before passing
    them to the :py:class:`Action` initializers.

    Parameters
    ----------
    pointers
        Unexpanded pointers that the strategy may put in the resulting
        hypertext.

    Returns
    -------
    A strategy that generates hypertext. The generated hypertext will be empty
    sometimes.
    """
    protected_pointers = st.sampled_from(pointers).map(lambda p: p + " ")
    # Protected from being garbled by following text: $1␣non-pointer text
    leaves = st.lists(ht_text | protected_pointers, min_size=1).map(join)
    # Concerning min_size see the comment above ht_text.
    return st.recursive(
        leaves,
        lambda subtree: st.lists(subtree | expanded_pointer(subtree),
                                 min_size=1).map(join)
    ).map(lambda s: s.strip())


def question_hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating hypertext that is suited for questions.

    Some hypertexts are likely to create infinite loops when used as a
    subquestion. See issue #15. This procedure returns the same strategy as
    :py:func:`hypertext`, except that it filters out those unsuitable cases.

    See also
    --------
    :py:func:`hypertext`
    """
    return hypertext(pointers).filter(lambda s: not s.startswith("["))


# Test case ################################################

class PatchworkStateMachine(RuleBasedStateMachine):
    """Bombard patchwork with random questions, replies etc.

    This test doesn't contain any assertions, yet, but at least it makes sure
    that no action will cause an unexpected exception.
    """
    def __init__(self):
        super(PatchworkStateMachine, self).__init__()
        self.db: Optional[Datastore] = None
        self.sess: Optional[RootQuestionSession] = None


    @property
    def context(self) -> Context:
        return self.sess.current_context


    def pointers(self) -> List[str]:
        """Return a list of the pointers available in the current context."""
        return list(self.context.name_pointers_for_workspace(
                        self.context.workspace_link, self.db)
                    .keys())


    def locked_pointers(self) -> List[str]:
        return [pointer
                for pointer, address in self.context.name_pointers.items()
                if address not in self.context.unlocked_locations]


    # TODO: Make the waiting time for the join adaptive.
    # TODO: If we call t.terminate() after the thread has finished (because
    # it finished just after the timeout), we get an error. Avoid or catch that.
    def act(self, action: Action):
        t = killable_thread.ThreadWithExc(target=lambda: self.sess.act(action),
                                          name="Killable Session.act",
                                          daemon=False)
        t.start()
        waiting_time = 0.5
        t.join(waiting_time)

        if t.is_alive():
            logging.info("Terminating the execution of action %s, because it"
                         " might be caught in an infinite loop (execution time"
                         " > %s s).", action, waiting_time)
            try:
                t.terminate()
            except killable_thread.UnkillableThread:
                sys.exit("Couldn't kill the thread that is executing action {}."
                         " Aborting in order to avoid system overload."
                         .format(action))


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
            self.sess.__exit__()
            self.sess = None


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def reply(self, data: SearchStrategy[Any]):
        self.act(
            Reply(data.draw(hypertext(self.pointers()))))
        if self.sess.root_answer:
            self.sess.__exit__()
            self.sess = None


    # TODO assertion: Unlocking already unlocked pointers causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def unlock(self, data: SearchStrategy[Any]):
        self.act(
            Unlock(data.draw(st.sampled_from(self.locked_pointers()))))


    # TODO: Move the try-except to self.act(), because the infinite loop
    # error can also occur with other actions. Cf.
    # https://github.com/oughtinc/patchwork/issues/12#issuecomment-404002144.
    # TODO assertion: Infinite loop error is only thrown when it should be
    # thrown.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def ask(self, data: SearchStrategy[Any]):
        question = data.draw(question_hypertext(self.pointers()))
        try:
            self.act(
                AskSubquestion(question))
        except ValueError as e:
            if "Action resulted in an infinite loop" not in str(e):
                raise


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def scratch(self, data: SearchStrategy[Any]):
        self.act(
            Scratch(data.draw(hypertext(self.pointers()))))


# Runner ###################################################

TestRandomly = PatchworkStateMachine.TestCase
