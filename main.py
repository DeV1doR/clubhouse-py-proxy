import logging
import asyncio

from fastapi import FastAPI, WebSocket
from clubhouse.clubhouse import Clubhouse


app = FastAPI()
logger = logging.getLogger(__name__)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt='%m/%d/%Y %I:%M:%S',
                    level=logging.INFO)


def check_auth(ch):
    if not (ch.HEADERS.get("CH-UserID") and
            ch.HEADERS.get("CH-DeviceId") and
            ch.HEADERS.get("Authorization")):
        raise Exception('Not Authenticated')


def get_creds(ch):
    return {
        'user_id': ch.HEADERS.get("CH-UserID"),
        'user_token': ch.HEADERS.get("Authorization"),
        'user_device': ch.HEADERS.get("CH-DeviceId"),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    loop = asyncio.get_event_loop()

    ch = Clubhouse()

    while True:
        data = await websocket.receive_json()
        logger.info(f'Receive data: {data}')
        try:
            id_, method, params, _ = data['id'], \
                data['method'], data['params'], data['jsonrpc']
        except KeyError:
            await websocket.send_json({
                'id': data.get('id', 0),
                'result': None,
                'error': {
                    'message': 'Invalid rpc 2.0 structure',
                    'code': -32602
                }
            })
            continue


        try:
            logger.info(f'Got method "{method}" with params "{params}"')
            if method == 'authenticate':
                ch = Clubhouse(*params)
                # just test authorization
                check_auth(ch)
                logger.info(f'Updating creds for user #{params[0]}')
                await websocket.send_json({
                    'id': 'auth',
                    'result': get_creds(ch),
                    'error': None
                })
                continue
            response = await loop.run_in_executor(None, lambda: getattr(ch, method)(*params))
        except AttributeError as e:
            logger.exception(e)
            await websocket.send_json({
                'id': id_,
                'result': None,
                'error': {
                    'message': 'Method not found',
                    'code': -32601
                }
            })
            continue
        except TypeError as e:
            logger.exception(e)
            await websocket.send_json({
                'id': id_,
                'result': None,
                'error': {
                    'message': e.args[0],
                    'code': -1
                }
            })
            continue
        except Exception as e:
            logger.exception(e)
            if 'Not Authenticated' in e.args[0]:
                ch = Clubhouse()
                await websocket.send_json({
                    'id': id_,
                    'result': None,
                    'error': {
                        'message': 'Not Authenticated',
                        'code': -32600
                    }
                })
            else:
                await websocket.send_json({
                    'id': id_,
                    'result': None,
                    'error': {
                        'message': 'Internal server error',
                        'code': -32000
                    }
                })
            continue

        await websocket.send_json({
            'id': id_,
            'result': response,
            'error': None
        })

        if method == 'complete_phone_number_auth' and 'auth_token' in response:
            clubhouse_creds = {
                'user_id': response['user_profile']['user_id'],
                'user_token': response['auth_token'],
                'user_device': ch.HEADERS['CH-DeviceId'],
            }
            ch = Clubhouse(**clubhouse_creds)
            logger.info(f'Updating creds for user #{clubhouse_creds["user_id"]}')
            await websocket.send_json({
                'id': 'auth',
                'result': clubhouse_creds,
                'error': None
            })
