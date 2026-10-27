"""Run the agent off the request thread, one message at a time per group.

A reply takes 10–25 s, so the webhook answers GroupMe at once and queues the message. Each group gets
its own worker thread: messages in one chat are handled in order (two at once would both load the same
history and one turn would be lost), while different groups don't wait on each other.

Queues live in this process, so run Django as a single process (threads are fine). More processes or
machines need a shared queue instead.
"""

import logging
import queue
import threading

from django.db import close_old_connections

from bot.services import handle_callback

log = logging.getLogger(__name__)
_queues: dict[str, queue.Queue] = {}
_lock = threading.Lock()


def enqueue(payload: dict) -> None:
    group_id = str(payload.get("group_id"))
    with _lock:
        q = _queues.get(group_id)
        if q is None:
            q = _queues[group_id] = queue.Queue()
            threading.Thread(target=_drain, args=(q,), name=f"groupme-{group_id}", daemon=True).start()
    q.put(payload)


def _drain(q: queue.Queue) -> None:
    while True:
        payload = q.get()
        close_old_connections()
        try:
            outcome = handle_callback(payload)
            log.info("GroupMe message %s: %s", payload.get("id"), outcome)
        except Exception:
            log.exception("Worker failed on GroupMe message %s", payload.get("id"))
        finally:
            close_old_connections()
            q.task_done()
