from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.deps import get_event_bus
from app.ws.event_bus import EventBus

router = APIRouter()

@router.websocket("/api/jobs/{job_id}/events")
async def job_events(ws: WebSocket, job_id: str, bus: EventBus = Depends(get_event_bus)):
    await ws.accept()
    await ws.send_json({"type": "replay", "events": bus.replay(job_id)})
    queue = bus.subscribe(job_id)
    try:
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(job_id, queue)
