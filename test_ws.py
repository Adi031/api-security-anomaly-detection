import asyncio
import websockets

async def test():
    try:
        async with websockets.connect('ws://localhost:8001/ws/live') as ws:
            print('Connected!')
            # wait a bit
            await asyncio.sleep(2)
            print('Still connected!')
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
