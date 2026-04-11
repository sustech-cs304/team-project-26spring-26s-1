from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/onebot/ws")
async def onebot_reverse_websocket(websocket: WebSocket):
    hub = websocket.app.state.OneBotHub
    await hub.serve(websocket)
