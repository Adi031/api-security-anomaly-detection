import asyncio
import websockets

async def test():
    try:
        async with websockets.connect('ws://localhost:8001/ws/live') as ws:
            print('Connected! Waiting for messages...')
            while True:
                msg = await ws.recv()
                print("Received:", msg)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
