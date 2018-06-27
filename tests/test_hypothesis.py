import hypothesis.strategies as st
from hypothesis.stateful import precondition, rule, RuleBasedStateMachine

from patchwork.actions import Reply
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler


# [ starts an expanded pointer and $ starts a locked pointer. Currently there is
# no way of escaping them.
ht_text = st.text().filter(lambda s: '[' not in s and '$' not
                                                   in s)

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

st.lists(st.one_of(ht_text, st.integers()))


def ht_base(pointers):
    return st.lists(ht_text | st.sampled_from(pointers)) \
                .map(lambda l: " ".join(l))


def expanded_pointer(ht):
    return ht.map(lambda ht_: "{}".format(ht_))


def hypertext(pointers):
    return st.recursive(ht_base(pointers),
                        lambda base: st.lists(base | expanded_pointer(
                                base)).map(lambda l: " ".join(l)))



class RandomExercise(RuleBasedStateMachine):
    def __init__(self):
        super(RandomExercise, self).__init__()
        self.db: Datastore              = None
        self.sess: RootQuestionSession  = None

    @precondition(lambda self: not self.sess)
    @rule(root_question=hypertext)
    def start_session(self, root_question: str):
        self.db     = Datastore()
        self.sess   = RootQuestionSession(Scheduler(self.db), root_question)

    @precondition(lambda self: self.sess)
    @rule(answer=hypertext,
          is_reset_db=st.booleans())
    def reply(self, answer: str, is_reset_db: bool):
        self.sess.act(Reply(answer))
        if self.sess.final_answer_promise:
            self.sess = None
            if is_reset_db:
                self.db = None


TestHypothesis = RandomExercise.TestCase
