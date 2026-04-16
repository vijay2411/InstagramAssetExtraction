import asyncio
from fastapi.testclient import TestClient
from app import deps
from app.main import app
from app.ws.event_bus import EventBus

def test_ws_replay_on_connect():
    """
    End-to-end check that the WS endpoint accepts a connection and sends the
    replay frame containing previously-buffered events. Live streaming across
    the test-thread / app-thread boundary is not covered here because EventBus
    queues are bound to the loop that created them. Live streaming is exercised
    by Task 5's EventBus unit tests within a single loop, and by Task 27's e2e.
    """
    bus = EventBus()

    async def seed():
        await bus.publish("j1", {"type": "stage.start", "stage": "download"})
        await bus.publish("j1", {"type": "stage.progress", "stage": "download", "progress": 0.5})
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(seed())

    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/api/jobs/j1/events") as ws:
                first = ws.receive_json()
                assert first["type"] == "replay"
                assert len(first["events"]) == 2
                assert first["events"][0]["stage"] == "download"
    finally:
        app.dependency_overrides.clear()

def test_ws_replay_empty_when_no_events():
    bus = EventBus()
    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/api/jobs/never/events") as ws:
                first = ws.receive_json()
                assert first["type"] == "replay"
                assert first["events"] == []
    finally:
        app.dependency_overrides.clear()
