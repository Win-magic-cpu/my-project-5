import asyncio


class SenderLockRegistry:
    """按 sender_id 提供互斥锁。

    对话状态是"读 → 改 → 写"三步，同一用户的两条消息如果并发执行，
    会读到同一份快照并互相覆盖（lost update）。用一把按用户粒度的锁
    把这三步包起来，代价是同一用户的消息串行，不同用户互不影响。
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, sender_id: str) -> asyncio.Lock:
        return self._locks.setdefault(sender_id, asyncio.Lock())

    @property
    def size(self) -> int:
        return len(self._locks)
