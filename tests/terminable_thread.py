"""Defines a thread that can be terminated from the outside.

Main class: :py:class:`TerminableThread`

Based on:
https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
Which in turn is based on:
http://tomerfiliba.com/recipes/Thread2/
Mixed in:
https://stackoverflow.com/questions/2829329/catch-a-threads-exception-in-the-caller-thread-in-python
"""

import ctypes
import sys
import threading


class ThreadExit(Exception):
    """Injected into the thread in order to make it terminate."""
    pass

class TerminationError(Exception):
    """Raised when a thread keeps running even after injecting :py:exc:`ThreadExit`.
    """
    pass


class TerminableThread(threading.Thread):
    """Like :py:class:`threading.Thread`, but can be killed from the outside.

    The semantics are the same as those of :py:class:`threading.Thread`, except
    that the method :py:meth:`TerminableThread.terminate` is added and if the
    child thread raised an exception, :py:meth:`TerminableThread.join` will
    re-raise it.
    """

    def __init__(self, *args, **kwargs):
        super(TerminableThread, self).__init__(*args, **kwargs)
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
            # Credits: threading source
            del self._target, self._args, self._kwargs


    def join(self, timeout=None):
        super(TerminableThread, self).join(timeout)
        if self.exc_info:
            raise self.exc_info[1]
        return self.result


    def _raise_exception(self, exc_type: type):
        """Raise exception with the given type in the thread represented by self.

        If the thread is waiting for a system call (eg. ``time.sleep()``,
        ``socket.accept()``) to return, it will ignore the exception.
        """
        lident = ctypes.c_long(self.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    lident,
                    ctypes.py_object(exc_type))

        if res == 0:
            raise ValueError("PyThreadState_SetAsyncExc failed to find {}."
                             .format(self))

        if res != 1:
            # "if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"
            # (https://svn.python.org/projects/stackless/Python-2.4.3/dev/Python/pystate.c)
            ctypes.pythonapi.PyThreadState_SetAsyncExc(lident, None)
            raise SystemError("PyThreadState_SetAsyncExc failed for {}."
                              .format(self))


    def terminate(self, timeout=0.01):
        self._raise_exception(ThreadExit)
        if timeout is not None:
            self.join(timeout)
            if self.is_alive():
                raise TerminationError("Attempted to terminate {}, but it keeps"
                                       " running.".format(self))
