import unittest

from patchwork.actions import Reply, Unlock
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler

class Issue004Test(unittest.TestCase):
    def test(self):
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "what is the sum of list [[6] []]") as sess:
            sess.act(Unlock("$3"))
            sess.act(Reply("6"))

        with RootQuestionSession(sched, "what is the sum of list [[6] []]") as sess:
            self.assertTrue(sess.is_fulfilled())

        with RootQuestionSession(sched, "what is the sum of list [[6] [[7] []]]") as sess:
            self.assertIsNotNone(sess.current_context)


if __name__ == '__main__':
    unittest.main()
