from typing import Any, Optional

import hypothesis.strategies as st
from hypothesis.searchstrategy import SearchStrategy
from hypothesis.stateful import precondition, rule, RuleBasedStateMachine

from patchwork.actions import Reply, Unlock, AskSubquestion, Scratch
from patchwork.context import Context
from patchwork.datastore import Datastore
from patchwork.hypertext import Workspace
from patchwork.scheduling import RootQuestionSession, Scheduler

# MAYBE TODO: Make sure that issues #11, #12 and #15 are tested. But maybe not,
# because once they're fixed, they're fixed and the chance of messing them up
# again is small.
# But an easy way of testing at least #15 is to assert in ask() that
# patchwork throws an error when the question is "$1" (question pointer).

# Also issue #4. – When the root question returns immediately, make sure the
# question was already in the DB.

# [ starts an expanded pointer and $ starts a locked pointer. Currently there is
# no way of escaping them.
# min_size 1, because otherwise AskSubquestion misbehaves.
ht_text = st.text(min_size=1).filter(lambda s: '[' not in s and ']' not in s
                                               and '$' not in s)


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
def locked_pointers(c: Context):
    ul = c.unlocked_locations.copy()
    #ul.remove(c.workspace_link)
    lp = [p for p, a in c.name_pointers.items() if a not in ul]
    return lp


class RandomExercise(RuleBasedStateMachine):
    def __init__(self):
        super(RandomExercise, self).__init__()
        self.db:    Optional[Datastore]             = None
        self.sess:  Optional[RootQuestionSession]   = None


    def pointers(self):
        context         = self.sess.current_context
        names_pointers  = context.name_pointers_for_workspace(
                                context.workspace_link, self.db)
        return list(names_pointers.keys())


    def question_pointer(self):
        context = self.sess.current_context
        ws: Workspace = self.db.dereference(context.workspace_link)
        return context.pointer_names[ws.question_link]


    @precondition(lambda self: not self.sess)
    @rule(data=st.data(),
          is_reset_db=st.booleans())
    def start_session(self, data: SearchStrategy[Any], is_reset_db: bool):
        if self.db is None or is_reset_db:
            self.db = Datastore()
        self.sess = RootQuestionSession(Scheduler(self.db),
                                        data.draw(hypertext([])))


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def reply(self, data: SearchStrategy[Any]):
        self.sess.act(Reply(data.draw(hypertext(self.pointers()))))
        if self.sess.final_answer_promise:
            self.sess = None


    # MAYBE TODO: Also try unlocking already unlocked pointers and assert
    # that it causes an exception.
    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def unlock(self, data: SearchStrategy[Any]):
        lp = locked_pointers(self.sess.current_context)
        sample_pointer = data.draw(st.sampled_from(lp))
        self.sess.act(Unlock(sample_pointer))


    @precondition(lambda self: self.sess)
    @rule(data=st.data())
    def ask(self, data: SearchStrategy[Any]):
        qp = self.question_pointer()
        question = data.draw(hypertext(self.pointers())
                             .filter(lambda q: q != qp))
        try:
            self.sess.act(AskSubquestion(question))
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
        self.sess.act(Scratch(data.draw(hypertext(self.pointers()))))


TestHypothesis = RandomExercise.TestCase
