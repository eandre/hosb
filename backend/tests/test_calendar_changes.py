"""Following a change in this process, whether or not the topic delivers it."""

import asyncio

import calendar_changes as cc


async def wait_for(check, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("still not so")
        await asyncio.sleep(0.01)


async def test_a_change_is_followed_here_even_when_publishing_fails(monkeypatch):
    seen: list[cc.CalendarChange] = []

    async def handler(change: cc.CalendarChange) -> None:
        seen.append(change)

    async def publish_fails(change: cc.CalendarChange) -> None:
        raise RuntimeError("the topic is down")

    monkeypatch.setattr(cc, "LOCAL_HANDLERS", [handler])
    monkeypatch.setattr(cc, "_publish", publish_fails)
    await cc.notify(user_id="user_ada", event_id=7)
    await wait_for(lambda: seen)
    assert seen == [cc.CalendarChange(user_id="user_ada", event_id=7)]


async def test_a_failing_handler_is_logged_not_raised(monkeypatch, caplog):
    async def handler(change: cc.CalendarChange) -> None:
        raise ValueError("Google is down")

    async def publish(change: cc.CalendarChange) -> None:
        pass

    monkeypatch.setattr(cc, "LOCAL_HANDLERS", [handler])
    monkeypatch.setattr(cc, "_publish", publish)
    await cc.notify(event_id=7)
    await wait_for(lambda: not cc._running)
    assert "background work failed" in caplog.text
