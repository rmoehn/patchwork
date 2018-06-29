import copy
from typing import Any, Optional

import hypothesis.strategies as st
from hypothesis.searchstrategy import SearchStrategy
from hypothesis.stateful import precondition, rule, RuleBasedStateMachine

from patchwork.actions import Reply, Unlock, AskSubquestion
from patchwork.context import Context
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler

# MAYBE TODO: Make sure that issues #11 and #12 are tested. But maybe not,
# because once they're fixed, they're fixed and the chance of messing them up
# again is small.

# [ starts an expanded pointer and $ starts a locked pointer. Currently there is
# no way of escaping them.
# min_size 1, because otherwise AskSubquestion misbehaves.
ht_text = st.text(min_size=1).filter(lambda s: '[' not in s and '$' not in s)

# st.builds
# st.recursive
# st.composite

# Can I pass an argument to a strategy? Yes, if I use draw(), but that way I
# can't use @example. And the output is different, if I understand it right.
# After each act(), I can put the available pointers (locked and unlocked) in
# a bundle. Nah, but I can't delete anything from a bundle.

# So I have to use a GenericStateMachine? But for that I can't use @example
# etc. either.

# So how do we make hypertext?
# We generate a list with elements randomly chosen between text and expanded
# pointers and unexpanded pointers.
# Unexpanded pointers are chose from a parameter.
# Expanded pointers consist of an opening bracket, hypertext and a closing
# bracket.


def ht_base(pointers):
    return st.lists(ht_text | st.sampled_from(pointers),
                    min_size=1) \
                .map(lambda l: " ".join(l))


def expanded_pointer(ht):
    return ht.map(lambda ht_: "{}".format(ht_))


# Concerning min_size see comment above ht_text.
def hypertext(pointers):
    return st.recursive(ht_base(pointers),
                        lambda base: st.lists(base | expanded_pointer(
                                base), min_size=1).map(lambda l: " ".join(l)))


# TODO: Collect statistics on the available pointers. Is there an overhang in
# any type of pointer that we should avoid by weighted sampling?
def locked_unlocked_pointers(c: Context):
    ul = copy.copy(c.unlocked_locations)
    ul.discard(c.workspace_link)
    up = [c.pointer_names[a] for a in ul]
    lp = [p for p, a in c.name_pointers.items() if a not in ul]
    return lp, up


class RandomExercise(RuleBasedStateMachine):
    def __init__(self):
        super(RandomExercise, self).__init__()
        self.db: Optional[Datastore]                = None
        self.sess: Optional[RootQuestionSession]    = None

    @precondition(lambda self: not self.sess)
    @rule(data=st.data())
    def start_session(self, data: SearchStrategy[Any]):
        self.db     = Datastore()
        self.sess   = RootQuestionSession(Scheduler(self.db),
                                          data.draw(hypertext([])))


    # FIXME: Resetting the DB should be done properly and in start_session.
    @precondition(lambda self: self.sess)
    @rule(data=st.data(),
          is_reset_db=st.booleans())
    def reply(self, data: SearchStrategy[Any], is_reset_db: bool):
        context: Context = self.sess.current_context
        pointers = context.name_pointers_for_workspace(context.workspace_link,
                                                       self.db)
        self.sess.act(Reply(data.draw(hypertext(list(pointers.keys())))))
        if self.sess.final_answer_promise:
            self.sess = None
            if is_reset_db:
                self.db = None


    # MAYBE TODO: Also try unlocking already unlocked pointers and assert
    # that it causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def unlock(self, data: SearchStrategy[Any]):
        lp, __ = locked_unlocked_pointers(self.sess.current_context)
        sample_pointer = data.draw(st.sampled_from(lp))
        self.sess.act(Unlock(sample_pointer))


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def ask(self, data: SearchStrategy[Any]):
        context: Context = self.sess.current_context
        pointers = context.name_pointers_for_workspace(context.workspace_link,
                                                       self.db)

        try:
            self.sess.act(AskSubquestion(
                                data.draw(hypertext(list(pointers.keys())))))
        except ValueError as e:
            # If it re-asked an ancestor's question...
            # (For now we'll prevent this error only in this primitive way.)
            if "Action resulted in an infinite loop" in str(e):
                pass
            else:
                raise



TestHypothesis = RandomExercise.TestCase
