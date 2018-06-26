import hypothesis.strategies as st
from hypothesis.stateful import precondition, rule, RuleBasedStateMachine

from patchwork.actions import Reply
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler


hypertext = st.text().filter(lambda s: '[' not in s and '$' not in s)

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
