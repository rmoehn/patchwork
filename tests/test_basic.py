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
            self.assertIsNotNone(sess.root_answer)
            self.assertIn("1761669", result)


    # The following tests are incomplete in that they only make sure that no
    # exceptions are thrown. Since the scheduler throws an exception when there
    # are no blocking contexts left, this implicitly asserts that the scheduler
    # doesn't overlook blocking contexts.

    def testRootReplyWithPointers(self):
        """Test whether root replies with pointers work."""
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "Root?") as sess:
            subquestions = ["Sub1?", "Sub2?"]
            for s in subquestions:
                sess.act(AskSubquestion(s))
            sess.act(Reply("Root [{} {}].".format(
                    *[sq.pointer for sq in
                      sess.current_context.to_data()['subquestions']])))
            self.assertIsNone(sess.root_answer)
            self.assertIn(sess.current_context.to_data()['question'],
                          subquestions)


        run_scenario("Root?",
                     [{'question': "Sub1?",
                       'answer': "Sub1.",
                       'unlock': 'after-root'},
                      {'question': "Sub2?",
                       'answer': "Sub2.",
                       'unlock': 'after-root'}],
                     "Root [$a1 $a2].")


    def testNonRootPromise(self):
        """Test whether a non-root promise gets advanced."""
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "Root?") as sess:
            s1 = ask("Sub1?")
            s2 = ask("Sub2 ({})?", s1.answer)
            reply("{}", s2.workspace)
            expect_context(s2)
            unlock(s2.question.links[0])
            expect_context(s1)
            reply("Sub1.")
            expect_context(s2)
            reply("Sub2 ({}).", s1.answer)
            expect_finished()
            expect_answer("Sub2 (Sub1.).")


            sess.act(AskSubquestion("Sub1?"))
            sess.act(AskSubquestion("Sub2 ({})?".format(
                    sess.current_context.to_data()['subquestions'][0].pointer)))


            sess.act(Reply(sess.current_context.to_data()['subquestions'][0].pointer))
            # End up in the context of Sub2.
            self.assertEqual(sess.current_context.to_data()['question'],
                             "Sub2 ($x)?")
            sess.act(Unlock("$x"))
            # End up in the context of Sub1.
            sess.act(Reply("Sub1."))
            # Context of Sub1.
            # Question should now be "Sub2 [$x: Sub1.]?".
            sess.act(Reply("It was Mietzekats $x."))

        # Problem: Tests have to extract the right pointer names and assign
        # their own symbols. Otherwise (if we use $a1, $3 etc. explicitly in
        # the tests), we will be tightly coupled with the implementation.

        # I thought of doing unit tests. But these *are* unit tests for the
        # scheduler. We don't get around having to deal with strings.

        # How much of this kind of tests do we need? Is it worth putting a
        # lot of effort into parsing stuff and building helpers etc.?

        # Why do I want integration tests?
        # - Because users will describe expected and actual behaviours at the
        #   integration level.
        # - Because that seems to be the level at which constructing
        #   tests is easiest.
        # - Because it's somewhat hard to do unit tests. Really? At least
        #   it's annoying.

        # It should be easy to write property-based tests, shouldn't it?
        # At least to write tests that execute all manner of valid actions.

        # If I do that well, they would cover all the other cases.

        # The most readable integration tests would just record sessions and
        # compare the expected to the actual string output. This is brittle.
        # But for small scenarios, it should be easy to just redo them when
        # some output detail changes.

        # In this case it would be cool if we could just copy in an
        # interactive session and make sure that the same happens again.

        # Okay, what would we need to do for property-based tests?
        # - Randomly generate a root question.
        # - Randomly generate actions.
        # - But with certain restrictions.
        # - Randomly generate hypertexts.
        # - Randomly reset the database.
        # - Make sure that session finish sometimes, and not only from the root
        #   context.
        # Randomly generating hypertext
        # - Consists of text and pointers.
        # - Pointers can be expanded pointers or unexpanded pointers to
        #   anything that is available in the current context.
        # - Expanded pointers contain hypertext.

        # Scratch
        # - Can put any hypertext at any time.

        # AskSubquestion
        # - Can put any hypertext at any time.

        # Reply.
        # - Can put any hyptertext at any time.

        # Unlock.
        # - Can pass any pointer that is locked in the current workspace.

    def testUnlockWorkspace(self):
        """Test unlocking of unfulfilled workspaces."""
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "Root?") as sess:
            sess.act(AskSubquestion("Sub1?"))
            sess.act(Unlock("$w1"))
