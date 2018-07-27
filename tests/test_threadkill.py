import concurrent.futures
import time


def ask_za_question(sess):
    sess.act(AskSubquestion("[What about $1?]"))


if __name__ == '__main__':
    from patchwork.actions import AskSubquestion
    from patchwork.datastore import Datastore
    from patchwork.scheduling import Scheduler, RootQuestionSession

    db = Datastore()
    sched = Scheduler(db)
    with RootQuestionSession(sched, "[0]") as sess:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ask_za_question, sess)
            __, not_done = concurrent.futures.wait([future], timeout=1)
            if future in not_done:
                print("Have to cancel the future.")
                can_be_cancelled = future.cancel()
                if can_be_cancelled:
                    print("CBC")
                else:
                    print("CNBC")

                for __ in range(10):
                    is_done = future.done()
                    if is_done:
                        print("Done.")
                        break
                    else:
                        print("Not done.")
                        time.sleep(1)
