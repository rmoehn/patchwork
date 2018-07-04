"""Run Hypothesis test many times.

I wrote this in order to debug an endless loop that occurred intermittently.
"""

import multiprocessing
import time
import unittest


from tests import test_hypothesis

def run_test(i_run):
    result = unittest.TestResult()
    test_hypothesis.TestHypothesis().run(result)
    print(result)
    return i_run

# Actually I don't want abort at timeout, but let it running, so that I can
# attach with pyflame.

def print_status(status):
    print("|{}|".format("".join(status)))

# What do I want?
# - Always four jobs running.
# - When one finishes, start the next.
# - When one is taking too long, don't start anything new. Just keep checking
#   it periodically.
def main():
    print(run_test(0))
    with multiprocessing.Pool(processes=4) as pool:
        n_trials    = 40
        results     = set()
        status      = [" " for __ in range(n_trials)]
        results     = [pool.apply_async(run_test, [i]) for i in range(n_trials)]
        times       = [0 for i in range(n_trials)]

        while True:
            for i, r in enumerate(results):
                if r.ready() and status[i] != "✔":
                    print(r.get())
                    status[i] = "✔"
            print_status(status)
            time.sleep(3)


if __name__ == '__main__':
    main()
