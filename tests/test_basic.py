import unittest

from patchwork.actions import AskSubquestion, Reply, Unlock
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler


# Note: This test is hard to read and tightly coupled with the implementation.
# Over the next week I will make refactorings and implement infrastructure to
# make it easy to write better tests. Or write more fine-grained unit tests
# instead. I haven't decided yet. (RM 2018-06-09)
class TestBasic(unittest.TestCase):
    """Integration tests for basic scenarios."""

    def testRecursion(self):
        """Test the recursion example from the taxonomy.

        Cf. https://ought.org/projects/factored-cognition/taxonomy#recursion
        """
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "What is 351 * 5019?") as sess:
            self.assertRegex(str(sess.current_context),
                             r"Question: .*What is 351 \* 5019\?")

            sess.act(AskSubquestion("What is 300 * 5019?"))
            context = sess.act(AskSubquestion("What is 50 * 5019?"))
            self.assertIn("$q1: What is 300 * 5019?", str(context))
            self.assertIn("$q2: What is 50 * 5019?", str(context))

            for pid in ["$a1", "$a2"]:  # pid = pointer ID
                context = sess.act(Unlock(pid))
                self.assertRegex(str(sess.current_context),
                                 r"Question: .*What is (?:300|50) \* 5019\?")
                if "300" in str(context):
                    context = sess.act(Reply("1505700"))
                else:
                    context = sess.act(Reply("250950"))

            self.assertIn("$a1: 1505700", str(context))
            self.assertIn("$a2: 250950", str(context))

            sess.act(AskSubquestion("What is 1505700 + 250950 + 5019?"))
            sess.act(Unlock("$a3"))
            context = sess.act(Reply("1761669"))

            self.assertIn("$q3: What is 1505700 + 250950 + 5019?", str(context))
            self.assertIn("$a3: 1761669", str(context))

            result = sess.act(Reply("1761669"))
            self.assertTrue(sess.is_fulfilled())
            self.assertIn("1761669", result)


    def testRootReplyWithPointers(self):
        """Incomplete test whether root replies with pointers work."""
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "Root?") as sess:
            sess.act(AskSubquestion("Sub1?"))
            sess.act(AskSubquestion("Sub2?"))
            sess.act(Reply("Root [$a1 $a2]."))
