import asyncio
import json

import aiohttp
from aiohttp import ClientError
from aiohttp.http_exceptions import HttpProcessingError
import async_timeout
import jsonrpc_base
from jsonrpc_base import TransportError


class Server(jsonrpc_base.Server):
    """A connection to a HTTP JSON-RPC server, backed by aiohttp"""

    def __init__(self, url, session=None, **connect_kwargs):
        super().__init__()
        self._session = session or aiohttp.ClientSession()

        # True if we made our own session
        self._internal_session = session is None

        self._client = None
        self._connect_kwargs = connect_kwargs
        self._url = url
        self._connect_kwargs['headers'] = self._connect_kwargs.get(
            'headers', {})
        self._connect_kwargs['headers']['Content-Type'] = (
            self._connect_kwargs['headers'].get(
                'Content-Type', 'application/json'))
        self._connect_kwargs['headers']['Accept'] = (
            self._connect_kwargs['headers'].get(
                'Accept', 'application/json-rpc'))
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
                pending_message = PendingMessage()
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
            self._client = await self._session.ws_connect(
                self._url, **self._connect_kwargs)
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Error connecting to server', None, exc)
        return self._session.loop.create_task(self._ws_loop())

    async def _ws_loop(self):
        """Listen for messages from the websocket server."""
        msg = None
        try:
            async for msg in self._client:
                if msg.type == aiohttp.WSMsgType.ERROR:
                    break
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        # If we get a binary message, try and decode it as a
                        # UTF-8 JSON string, in case the server is sending
                        # binary websocket messages. If it doens't decode we'll
                        # ignore it since we weren't expecting binary messages
                        # anyway
                        data = json.loads(msg.data.decode())
                    except ValueError:
                        continue
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                    except ValueError as exc:
                        raise TransportError('Error Parsing JSON', None, exc)
                else:
                    # This is tested with test_message_ping_ignored, but
                    # cpython's optimizations prevent coveragepy from detecting
                    # that it's run
                    # https://bitbucket.org/ned/coveragepy/issues/198/continue-marked-as-not-covered
                    continue  # pragma: no cover

                if 'method' in data:
                    request = jsonrpc_base.Request.parse(data)
                    response = await self.async_receive_request(request)
                    if response:
                        await self.send_message(response)
                else:
                    self._pending_messages[data['id']].response = data

        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', None, exc)
        finally:
            await self.close()
            if msg and msg.type == aiohttp.WSMsgType.ERROR:
                raise TransportError(
                    'Websocket error detected. Connection closed.')

    async def close(self):
        """Close the connection to the websocket server."""
        if self.connected:
            await self._client.close()
            self._client = None
        if self._internal_session:
            # If we created a clientsession for this Server, close it here.
            # And then instantiate a new clientsession in case the
            # connection should be reopened
            await self._session.close()
            self._session = aiohttp.ClientSession()

    @property
    def connected(self):
        """Websocket server is connected."""
        return self._client is not None


class PendingMessage(object):
    """Wait for response of pending message."""

    def __init__(self):
        self._event = asyncio.Event()
        self._response = None

    async def wait(self, timeout=None):
        with async_timeout.timeout(timeout):
            await self._event.wait()
            return self._response

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value
        self._event.set()
