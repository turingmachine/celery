import shelve

from celery.utils.compat import defaultdict
from celery.datastructures import LimitedSet

#: maximum number of revokes to keep in memory.
REVOKES_MAX = 10000

#: how many seconds a revoke will be active before
#: being expired when the max limit has been exceeded.
REVOKE_EXPIRES = 3600

#: set of all reserved :class:`~celery.worker.job.TaskRequest`'s.
reserved_requests = set()

#: set of currently active :class:`~celery.worker.job.TaskRequest`'s.
active_requests = set()

#: count of tasks executed by the worker, sorted by type.
total_count = defaultdict(lambda: 0)

#: the list of currently revoked tasks.  Persistent if statedb set.
revoked = LimitedSet(maxlen=REVOKES_MAX, expires=REVOKE_EXPIRES)


def task_reserved(request):
    """Updates global state when a task has been reserved."""
    reserved_requests.add(request)


def task_accepted(request):
    """Updates global state when a task has been accepted."""
    active_requests.add(request)
    total_count[request.task_name] += 1


def task_ready(request):
    """Updates global state when a task is ready."""
    active_requests.discard(request)
    reserved_requests.discard(request)


class Persistent(object):
    storage = shelve
    _open = None

    def __init__(self, filename):
        self.filename = filename
        self._load()

    def save(self):
        self.sync(self.db).sync()
        self.close()

    def merge(self, d):
        revoked.update(d.get("revoked") or {})
        return d

    def sync(self, d):
        prev = d.get("revoked") or {}
        prev.update(revoked.as_dict())
        d["revoked"] = prev
        return d

    def open(self):
        return self.storage.open(self.filename)

    def close(self):
        if self._open:
            self._open.close()
            self._open = None

    def _load(self):
        self.merge(self.db)
        self.close()

    @property
    def db(self):
        if self._open is None:
            self._open = self.open()
        return self._open
