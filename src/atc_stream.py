"""Bounded WebSocket delivery: one slow browser never stalls the radar feed."""
import asyncio
import json
import logging

log = logging.getLogger(__name__)


class WSManager:
    """Serialize each message once and give each connection its own writer.

    A full queue disconnects that client instead of losing radio events or
    accumulating stale states. Reconnecting obtains a fresh snapshot.
    """

    def __init__(self, queue_size=16, send_timeout=2.0):
        self.active = {}
        self._tasks = set()
        self._queue_size = queue_size
        self._send_timeout = send_timeout

    async def connect(self, ws, initial=None):
        await ws.accept()
        outgoing = asyncio.Queue(maxsize=self._queue_size)
        if initial is not None:
            outgoing.put_nowait(self._encode(initial))
        task = asyncio.create_task(self._writer(ws, outgoing))
        self.active[ws] = (outgoing, task)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        await asyncio.sleep(0)  # Start the writer so cancellation always runs its cleanup.

    @staticmethod
    def _encode(msg):
        return json.dumps(msg, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    def disconnect(self, ws):
        client = self.active.pop(ws, None)
        if client is not None:
            client[1].cancel()

    async def _writer(self, ws, outgoing):
        try:
            while True:
                message = await outgoing.get()
                await asyncio.wait_for(ws.send_text(message), self._send_timeout)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.info("WebSocket client disconnected: %s", exc)
        finally:
            self.active.pop(ws, None)
            try:
                await asyncio.wait_for(ws.close(code=1013), timeout=0.5)
            except Exception:
                pass  # The transport may already be closed by the browser.

    async def broadcast(self, msg):
        if not self.active:
            return
        message = self._encode(msg)
        for ws, (outgoing, _) in list(self.active.items()):
            try:
                outgoing.put_nowait(message)
            except asyncio.QueueFull:
                log.warning("WebSocket client too slow; bounded queue exhausted")
                self.disconnect(ws)

    async def shutdown(self):
        tasks = list(self._tasks)
        for ws in list(self.active):
            self.disconnect(ws)
        await asyncio.gather(*tasks, return_exceptions=True)
