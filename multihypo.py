"""Run Hypothesis test many times.

I wrote this in order to debug an endless loop that occurred intermittently.
"""

import collections
import multiprocessing
import time
import unittest

from tests import test_randomly

def run_test(i_run):
    result = unittest.TestResult()
    test_randomly.TestRandomly().run(result)
    print(result)
    return i_run, result.wasSuccessful()

# Actually I don't want to abort at timeout, but leave it running, so that I can
# attach with pyflame.

def print_status(status):
    print("|{}|".format("".join(status)))

# What do I want?
# - Always four jobs running.
# - When one finishes, start the next.
# - When one is taking too long, don't start anything new. Just keep checking
#   it periodically.
def main():
    with multiprocessing.Pool(processes=4) as pool:
        n_trials    = 40
        status      = [" " for __ in range(n_trials)]
        results     = [pool.apply_async(run_test, [i]) for i in range(n_trials)]

        while sum(1 for s in status if s != " ") < n_trials:
            for i, r in enumerate(results):
                if r.ready() and status[i] == " ":
                    __, was_successful = r.get()
                    status[i] = "✔" if was_successful else "✘"
            print_status(status)
            time.sleep(3)


if __name__ == '__main__':
    main()
