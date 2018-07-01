import unittest

from patchwork.actions import Reply, Unlock, AskSubquestion
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler


class Issue004Test(unittest.TestCase):
    def test(self):
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "what is the sum of list [[6] []]") as sess:
            sess.act(AskSubquestion("Bluuhu."))
            c = sess.act(Unlock("$3"))
            print(str(c))
            print(c.name_pointers_for_workspace())
            print(c.unlocked_locations_from_workspace(c.workspace_link, db))


            sess.act(Reply("6"))

        with RootQuestionSession(sched, "what is the sum of list [[6] []]") as sess:
            self.assertIsNotNone(sess.root_answer)

        with RootQuestionSession(sched, "what is the sum of list [[6] [[7] []]]") as sess:
            self.assertIsNotNone(sess.current_context)
