import asyncio
import pytest
from app.ws.event_bus import EventBus

@pytest.mark.asyncio
async def test_publish_buffers_event():
    bus = EventBus(buffer_size=10)
    await bus.publish("j1", {"type": "stage.start", "stage": "download"})
    assert len(bus.replay("j1")) == 1

@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    bus = EventBus(buffer_size=10)
    queue = bus.subscribe("j1")
    await bus.publish("j1", {"type": "stage.start", "stage": "download"})
    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg == {"type": "stage.start", "stage": "download"}

@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bus = EventBus(buffer_size=10)
    q1 = bus.subscribe("j1")
    q2 = bus.subscribe("j1")
    await bus.publish("j1", {"type": "x"})
    assert (await asyncio.wait_for(q1.get(), 1.0)) == {"type": "x"}
    assert (await asyncio.wait_for(q2.get(), 1.0)) == {"type": "x"}

@pytest.mark.asyncio
async def test_subscriber_for_different_job_isolated():
    bus = EventBus(buffer_size=10)
    q1 = bus.subscribe("j1")
    q2 = bus.subscribe("j2")
    await bus.publish("j1", {"type": "x"})
    assert not q2.qsize()
    assert (await asyncio.wait_for(q1.get(), 1.0))["type"] == "x"

@pytest.mark.asyncio
async def test_buffer_evicts_oldest_beyond_size():
    bus = EventBus(buffer_size=3)
    for i in range(5):
        await bus.publish("j1", {"i": i})
    replayed = bus.replay("j1")
    assert len(replayed) == 3
    assert replayed[0]["i"] == 2
    assert replayed[-1]["i"] == 4
