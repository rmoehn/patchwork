"""Property-based test for Patchwork.

Main class: :py:class:`PatchworkStateMachine`
"""
import os
import re
import time
from typing import Any, Collection, List, Optional
import unittest

import hypothesis.strategies as st
import multiprocessing
from hypothesis.searchstrategy import SearchStrategy
from hypothesis.stateful import RuleBasedStateMachine, precondition, rule

from patchwork.actions import AskSubquestion, Reply, Scratch, Unlock, Action
from patchwork.context import Context
from patchwork.datastore import Address, Datastore
from patchwork.hypertext import Workspace
from patchwork.scheduling import RootQuestionSession, Scheduler


# Strategies ###############################################

# A strategy for generating hypertext without any pointers, ie. just text.
#
# Notes:
# - [ and ] are for expanded pointers and $ starts a locked pointer. Currently
#   there is no way of escaping them, so filter them out.
# - min_size=1, because AskSubquestion misbehaves with empty questions. See also
#   issue #11.
from tests import killable_thread

ht_text = st.text(min_size=1).filter(lambda t: re.search(r"[\[\]$]", t) is None)


def expanded_pointer(hypertext_: SearchStrategy[str]) -> SearchStrategy[str]:
    """Turns a strategy generating hypertext into one generating pointers to it.

    An expanded pointer to hypertext "<some hypertext>" has the form "[<some
    hypertext>]".
    """
    return hypertext_.map(lambda ht_: "[{}]".format(ht_))


def join(l: List[str]) -> str:
    return "".join(l)


# Concerning min_size see the comment above ht_text.
def hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating nested hypertext.

    The resulting strategy can generate any hypertext. Ie. a mix of
    text, unexpanded pointers, and expanded pointers containing hypertext.
    The resulting string won't have whitespace at either end in order to be
    consistent with command-line Patchwork, which strips inputs before passing
    them to the Actions.

    Parameters
    ----------
    pointers
        Unexpanded pointers that the strategy may put in the resulting
        hypertext.

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
    ).map(lambda s: s.strip())


def nonempty_hypertext(pointers: List[str]) -> SearchStrategy[str]:
    """Return a strategy for generating non-empty hypertext.

    See also
    --------
    :py:func:`hypertext`
    """
    return hypertext(pointers).filter(lambda s: s)


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


class PatchworkStateMachine(RuleBasedStateMachine):
    """Bombard patchwork with random questions, replies etc.

    This doesn't contain any assertions, yet, but at least it makes sure that no
    action will cause an exception or infinite loop.
    """
    def __init__(self):
        super(PatchworkStateMachine, self).__init__()
        self.db: Optional[Datastore] = None
        self.sess: Optional[RootQuestionSession] = None
        self.pool = multiprocessing.Pool(processes=1)


    def pointers(self) -> List[str]:
        """Return a list of the pointers available in the current context."""
        c = self.sess.current_context
        names_pointers = c.name_pointers_for_workspace(c.workspace_link, self.db)
        return list(names_pointers.keys())


    def unaskable_pointers(self) -> Collection[str]:
        """Return pointers that by themselves can't be asked as a subquestion."""
        c = self.sess.current_context
        ws: Workspace = self.db.dereference(c.workspace_link)

        unaskable_addrs: List[Address] = [ws.question_link]
        if not self.db.dereference(ws.scratchpad_link):
            unaskable_addrs.append(ws.scratchpad_link)
        unaskable_addrs += [sq[0] for sq in ws.subquestions]  # sq[0]: question

        return {c.pointer_names[a] for a in unaskable_addrs}


    def act(self, action: Action):
        t = killable_thread.ThreadWithExc(target=lambda: self.sess.act(action),
                                          daemon=False)
        t.start()
        t.join(1)
        if t.is_alive():
            print("Have to kill at {}.".format(time.time()))
            try:
                t.raiseExc(RuntimeError)
            except Exception as e:
                print("Exception with the async kill: {}".format(e))
                os._exit(1)
        if t.is_alive():
            print("Couldn't kill at {}.".format(time.time()))
            os._exit(1)


    # TODO: We should have a Session.__exit__ somewhere.
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


    # TODO: After issue #12 is resolved, remove the workaround. It is too
    # restrictive.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def reply(self, data: SearchStrategy[Any]):
        reply = data.draw(hypertext(self.pointers()).filter(
                    lambda r: not re.match(r"\$q\d+\Z", r)))  # Issue #12, comment #2.
        self.act(
            Reply(reply))
        if self.sess.root_answer:
            self.sess = None


    # TODO assertion: Unlocking already unlocked pointers causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def unlock(self, data: SearchStrategy[Any]):
        lps = locked_pointers(self.sess.current_context)
        self.act(
            Unlock(data.draw(st.sampled_from(lps))))


    # TODO assertion: We should only get that value error when re-asking an
    # ancestor's question.
    # TODO assertion: Asking an unaskable pointer causes an exception.
    # TODO generation: Address
    # https://github.com/oughtinc/patchwork/issues/15#issuecomment-404728700.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def ask(self, data: SearchStrategy[Any]):
        up = self.unaskable_pointers()
        question = data.draw(question_hypertext(self.pointers())
                         .filter(lambda q: q not in up))  # Issue #15.
        try:
            self.act(
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
        self.act(
            Scratch(data.draw(hypertext(self.pointers()))))


# Runner ###################################################

TestRandomly = PatchworkStateMachine.TestCase
# def run_state_machine():
#     result = unittest.TestResult()
#     t1 = time.time()
#     PatchworkStateMachine.TestCase().run(result)
#     t2 = time.time()
#     print(result)
#     return result, t2 - t1
#
#
# class TestRandomly(unittest.TestCase):
#     def testRunStateMachine(self):
#         with multiprocessing.Pool() as pool:
#             n_runs = max(4, os.cpu_count())  # Feel free to adapt this for your purposes.
#             results = [pool.apply_async(run_state_machine) for i in range(n_runs)]
#
#             # What do I want?
#             # - I think the probability is high that at least one of four
#             #   runs finishes.
#             # - So we have the running time of at least one process as a
#             #   yardstick for the other processes.
#             # - If nothing has happened for four times the normal running
#             #   time, terminate the process pool.
#
#             # - Hmm, but I want the tests not to take forever, right? The
#             #   problem is that Hypothesis tests' run times vary, because
#             #   sometimes they hit a failure and shrink.
#             # - That's why it would be better to put a time limit on act().
#             #   I guess I should just try how much of a performance penalty
#             #   running only act() asynchronously incurs.
