import asyncio

import aiohttp
from aiohttp import ClientError
from aiohttp.http_exceptions import HttpProcessingError
import async_timeout
import jsonrpc_base
from jsonrpc_base import JSONRPCError, TransportError, ProtocolError


class Server(jsonrpc_base.Server):
    """A connection to a HTTP JSON-RPC server, backed by aiohttp"""

    def __init__(self, url, session=None, **connect_kwargs):
        super().__init__()
        object.__setattr__(self, 'session', session or aiohttp.ClientSession())
        self._client = None
        self._connect_kwargs = connect_kwargs
        self._url = url
        self._connect_kwargs['headers'] = self._connect_kwargs.get('headers', {})
        self._connect_kwargs['headers']['Content-Type'] = self._connect_kwargs['headers'].get(
            'Content-Type', 'application/json')
        self._connect_kwargs['headers']['Accept'] = self._connect_kwargs['headers'].get(
            'Accept', 'application/json-rpc')
        self._timeout = self._connect_kwargs.get('timeout')
        self._pending_messages = {}

    async def send_message(self, message):
        """Send the HTTP message to the server and return the message response.

        No result is returned if message is a notification.
        """
        if self._client is None:
            raise TransportError('Client is not connected.', message)

        try:
            await self._client.send_str(message.serialize())
            if message.response_id:
                pending_message = PendingMessage(loop=self.session.loop)
                self._pending_messages[message.response_id] = pending_message
                response = await pending_message.wait(self._timeout)
                del self._pending_messages[message.response_id]
            else:
                response = None
            return message.parse_response(response)
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', message, exc)

    async def ws_connect(self):
        """Connect to the websocket server."""
        if self.connected:
            raise TransportError('Connection already open.')

        try:
            self._client = await self.session.ws_connect(
                self._url, **self._connect_kwargs)
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Error connecting to server', None, exc)
        return self.session.loop.create_task(self._ws_loop())

    async def _ws_loop(self):
        """Listen for messages from the websocket server."""
        msg = None
        try:
            while True:
                msg = await self._client.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                    except ValueError as exc:
                        raise TransportError('Error Parsing JSON', None, exc)
                    if 'method' in data:
                        request = jsonrpc_base.Request.parse(data)
                        response = self.receive_request(request)
                        if response:
                            await self.send_message(response)
                    else:
                        self._pending_messages[data['id']].response = data
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', None, exc)
        finally:
            await self.close()
            if msg and msg.type == aiohttp.WSMsgType.ERROR:
                raise TransportError('Websocket error detected. Connection closed.')

    async def close(self):
        """Close the connection to the websocket server."""
        if self.connected:
            await self._client.close()
            self._client = None

    @property
    def connected(self):
        """Websocket server is connected."""
        return self._client is not None


class PendingMessage(object):
    """Wait for response of pending message."""

    def __init__(self, loop=None):
        self._loop = loop
        self._event = asyncio.Event(loop=loop)
        self._response = None

    async def wait(self, timeout=None):
        with async_timeout.timeout(timeout=timeout, loop=self._loop):
            await self._event.wait()
            return self._response

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value
        self._event.set()
