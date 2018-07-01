import pprint
from unittest import TestCase

from patchwork.actions import AskSubquestion
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler


class TestContext(TestCase):
    def test_to_data(self):
        db      = Datastore()
        sched   = Scheduler(db)
        with RootQuestionSession(sched, "Root?") as sess:
            sess.act(AskSubquestion("Sub?"))
            sess.act(AskSubquestion("SubPlus?"))
            pprint.pprint(sess.current_context.to_data(db))
            print()
            print(str(sess.current_context))

