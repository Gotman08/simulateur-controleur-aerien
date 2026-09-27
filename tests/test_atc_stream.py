"""Exercise delivery deadlines, saturation, order and connection cleanup."""
import asyncio
import json

from atc_stream import WSManager


class Socket:
    def __init__(self, blocked=False):
        self.blocked = blocked
        self.messages = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, message):
        if self.blocked:
            await asyncio.Event().wait()
        self.messages.append(json.loads(message))

    async def close(self, code):
        self.closed = True


def test_slow_client_does_not_block_healthy_client():
    async def run():
        manager = WSManager(send_timeout=0.05)
        slow, healthy = Socket(blocked=True), Socket()
        await manager.connect(slow)
        await manager.connect(healthy)
        await asyncio.wait_for(manager.broadcast({"type": "state", "t": 1}), 0.02)
        await asyncio.sleep(0.01)
        assert healthy.messages == [{"type": "state", "t": 1}]
        await asyncio.sleep(0.07)
        assert slow.closed and slow not in manager.active
        assert healthy in manager.active
        await manager.shutdown()
        assert healthy.closed and not manager.active and not manager._tasks
    asyncio.run(run())


def test_full_client_queue_disconnects_without_losing_event_silently():
    async def run():
        manager = WSManager(queue_size=2)
        slow = Socket(blocked=True)
        await manager.connect(slow, {"type": "state", "t": 0})
        for t in range(5):
            await manager.broadcast({"type": "exchange", "t": t})
        assert slow not in manager.active
        await manager.shutdown()
        assert slow.closed
    asyncio.run(run())


def test_initial_snapshot_and_events_are_ordered():
    async def run():
        manager = WSManager()
        sock = Socket()
        await manager.connect(sock, {"t": 0})
        for t in range(1, 5):
            await manager.broadcast({"t": t})
        await asyncio.sleep(0.02)
        assert [m["t"] for m in sock.messages] == list(range(5))
        manager.disconnect(sock)
        await manager.shutdown()
        assert sock.closed
    asyncio.run(run())
