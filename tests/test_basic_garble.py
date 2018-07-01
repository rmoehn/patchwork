import unittest

from patchwork.actions import Unlock, AskSubquestion
from patchwork.datastore import Datastore
from patchwork.scheduling import RootQuestionSession, Scheduler



class BasicTest(unittest.TestCase):
    """Integration tests for basic scenarios."""


    def run_context(self, context, expected):
        self.assertEqual(context.workspace_link.ques, expected['question'])
        # Make sure that the question at the top is all['question']
        # Randomly ask sub-questions and unlock sub-answers.
        #   When it's an Unlock, find out which of the sub-contexts we've
        #       ended up in and recurse
        #   When it's a sub-question, make sure that a new question is opened
        #       in the context.
        # Of course only as many Unlocks as Asks.
        # When all is asked and unlocked, reply.
        return sess.act(Reply(expected['reply']))


    def run_scenario(self, root_question, contexts, root_answer):
        all = {'question': root_question,
               'subs': contexts,
               'answer': root_answer}

        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, root_question) as sess:
            final_reply = self.run_context(sess.current_context, all)
            self.assertTrue(sess.is_fulfilled())
            self.assertIn("The final answer is:", final_reply)
            self.assertIn(root_answer, final_reply)





    def testLaziness(self):
        """
        Schedule context for which unlock is waiting, not top-of-stack context.
        """
        db      = Datastore()
        sched   = Scheduler(db)

        with RootQuestionSession(sched, "What is 351 * 5019?") as sess:
            sess.act(AskSubquestion("What is 300 * 5019?"))
            sess.act(AskSubquestion("What is 50 * 5019?"))


            run_scenario("What is 351 * 5019?",
                         [{'question':  "What is 300 * 5019?",
                           'answer':    "1505700"},
                          {'question':  "What is 50 * 5019?",
                           'answer':    "250950"},
                          {'question':  "What is 1505700 + 250950 +5019?",
                           'answer':    "1761669"}],
                         "1761669")

            # What should the code do?
            # - Make a session.
            # - Ask the root question.
            # - Ask the sub-questions.
            # - Unlock them.
            # - Verify that the question in a context is one of the ones

            self.assertIn(str(sess.act(Unlock("$a2"))), "300 * 5019?")
            is_descendant…
            self.assertTrue(is_successor)
            self.assertIn(str(sess.act(Reply("1505700"))))
            sess.act(AskSubquestion("Question 3?"))
            sess.act(AskSubquestion("Question 4?"))
            context = sess.act(Unlock("$a2"))
            self.assertIn("Question 2?", str(context))


if __name__ == '__main__':
    unittest.main()
