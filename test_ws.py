import asyncio
import websockets

async def test():
    try:
        async with websockets.connect('ws://127.0.0.1:8000/ws/live') as ws:
            print('Connected!')
            res = await ws.recv()
            print('Received data!')
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
