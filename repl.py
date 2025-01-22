import asyncio
import os
import json
import websockets
from aiohttp import web
from jupyter_client import KernelManager


km = KernelManager()

km.start_kernel()
kc = km.client()
kc.start_channels()

print(f"Kernel connection file written to {km.connection_file}")

all_messages = []


def fetch_kernel_messages():
    global all_messages
    latest_messages = []
    while kc.iopub_channel.msg_ready():
        msg = kc.get_iopub_msg()
        latest_messages.append(msg)

    all_messages += latest_messages
    return latest_messages


async def websocket_handler(websocket):
    try:
        for message in all_messages:
            print(f"Sending existing message: {message}")
            await websocket.send(json.dumps(message, indent=4, sort_keys=True, default=str))

        while True:
            latest_messages = fetch_kernel_messages()
            for message in latest_messages:
                print(f"Sending message: {message}")
                await websocket.send(json.dumps(message, indent=4, sort_keys=True, default=str))
            await asyncio.sleep(0.1)
    except websockets.exceptions.ConnectionClosedOK:
        print("WebSocket connection closed normally")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket connection closed with error: {e}")


async def handle_html_request(_request):
    with open("index.html", "r") as f:
        html_content = f.read()
    return web.Response(text=html_content, content_type="text/html")


async def start_websocket_server():
    async with websockets.serve(websocket_handler, "localhost", 8765) as server:
        await server.serve_forever()


async def start_http_server():
    app = web.Application()
    app.add_routes([web.get("/", handle_html_request)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()


async def main():
    websocket_server_task = asyncio.create_task(start_websocket_server())
    http_server_task = asyncio.create_task(start_http_server())

    try:
        while True:
            fetch_kernel_messages()
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        websocket_server_task.cancel()
        http_server_task.cancel()
        await websocket_server_task
        await http_server_task
        kc.stop_channels()
        km.shutdown_kernel()


if __name__ == "__main__":
    asyncio.run(main())
