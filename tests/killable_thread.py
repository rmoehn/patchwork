import ctypes
import threading

import sys
import traceback


class ThreadExit(Exception):
    pass

class UnkillableThread(Exception):
    pass

# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
# http://tomerfiliba.com/recipes/Thread2/
# https://svn.python.org/projects/stackless/Python-2.4.3/dev/Python/pystate.c
def _async_raise(tid: int, exc_type: type):
    """Raise an exception in the thread with ID ``tid``"""
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid),
                                                     ctypes.py_object(exc_type))
    if res == 0:
        raise ValueError("Couldn't find thread with ID {}.".format(tid))
    elif res != 1:
        # "if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

# https://stackoverflow.com/questions/2829329/catch-a-threads-exception-in-the-caller-thread-in-python

class ThreadWithExc(threading.Thread):
    '''A thread class that supports raising exception in the thread from
       another thread.
    '''

    def __init__(self, *args, **kwargs):
        super(ThreadWithExc, self).__init__(*args, **kwargs)
        self.exc_info = None
        self.result = None
        self.terminated = False

    def run(self):
        try:
            if self._target:
                self.result = self._target(*self._args, **self._kwargs)
        except ThreadExit:
            self.terminated = True
        except Exception:
            self.exc_info = sys.exc_info()
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            # (Copied from threading source.)
            del self._target, self._args, self._kwargs

    # The result should include that, but actually an exception.
    def join(self, timeout=None):
        super(ThreadWithExc, self).join(timeout)
        if self.exc_info:
            raise self.exc_info[1]
        return self.result

    def raise_exception(self, exc_type: type):
        """Raises the given exception type in the context of this thread.

        If the thread is busy in a system call (time.sleep(),
        socket.accept(), ...), the exception is simply ignored.

        If you are sure that your exception should terminate the thread,
        one way to ensure that it works is:

            t = ThreadWithExc( ... )
            ...
            t.raiseExc( SomeException )
            while t.isAlive():
                time.sleep( 0.1 )
                t.raiseExc( SomeException )

        If the exception is to be caught by the thread, you need a way to
        check that your thread has caught it.

        CAREFUL : this function is executed in the context of the
        caller thread, to raise an excpetion in the context of the
        thread represented by this instance.
        """
        _async_raise(self.ident, exc_type)

    def terminate(self, timeout=0.01):
        self.raise_exception(ThreadExit)
        if timeout is not None:
            self.join(timeout)
            if self.is_alive():
                raise UnkillableThread("Attempted to terminate thread '{}', but"
                                       " it keeps running.".format(self.getName()))
