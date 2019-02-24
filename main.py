import asyncio
from random import random
from typing import List

from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response, Application, WebSocketResponse
from logging import LogRecord
import logging.handlers
import janus

log = logging.getLogger(__package__)


async def root_page(request: Request):

    filename = 'root_page.html'
    with open(filename, 'r') as fh:
        return Response(body=fh.read(), content_type='text/html')


async def websocket_page(request: Request):

    websockets: List[WebSocketResponse] = app['websockets']
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    try:
        websockets.append(ws)
        log.debug(f'Подключен {ws}')
        async for msg in ws:
            print(f'websocket: {msg}')
    except Exception as e:
        log.warning(f'{e}')
    finally:
        log.debug(f'Отключен {ws}')
        websockets.remove(ws)
        await ws.close()


async def queue_to_websocket(app: Application):

    queue = app['log_queue'].async_q
    websockets: List[WebSocketResponse] = app['websockets']
    while True:
        try:
            log_record: LogRecord = await queue.get()
        except asyncio.CancelledError:
            app['log_queue'].close()
            return
        else:
            for ws in websockets:
                # print(f'>> websockets={len(websockets)} >> {ws}')
                await ws.send_str(log_record.msg)
        finally:
            queue.task_done()


async def test_log_flow(app: Application, log_every: int = 1):

    while True:
        log.info(random())
        await asyncio.sleep(log_every)


if __name__ == '__main__':

    app = web.Application()
    app['websockets'] = []

    loop = asyncio.get_event_loop()

    queue = janus.Queue(loop=loop)
    app['log_queue'] = queue

    log_handlers = (
        logging.StreamHandler(),
        logging.handlers.QueueHandler(queue.sync_q))
    logging.basicConfig(
        level=logging.DEBUG, handlers=log_handlers,
        format='%(asctime)s %(levelname)-7s %(message)s')

    app.add_routes([
        web.get('/ws', websocket_page),
        web.get('/', root_page),
    ])

    loop.create_task(queue_to_websocket(app))
    loop.create_task(test_log_flow(app))

    web.run_app(app, host='127.0.0.1')
