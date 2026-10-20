import asyncio
import json
import logging
import sys

import aiohttp
from aiohttp import ClientError
from aiohttp.http_exceptions import HttpProcessingError
import jsonrpc_base
from jsonrpc_base import TransportError
from multidict import CIMultiDict

_LOGGER = logging.getLogger(__name__)

if sys.version_info >= (3, 11):
    from asyncio import timeout as async_timeout
else:
    from async_timeout import timeout as async_timeout


class Server(jsonrpc_base.Server):
    """A connection to a HTTP JSON-RPC server, backed by aiohttp"""

    def __init__(self, url, session=None, *, timeout=None, **connect_kwargs):
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
        # Only used for waiting on responses, aiohttp's ws_connect() gets
        # its own timeout through the keyword arguments of ws_connect()
        self._timeout = timeout
        self._pending_messages = {}

    async def send_message(self, message):
        """Send the HTTP message to the server and return the message response.

        No result is returned if message is a notification.
        """
        if self._client is None:
            raise TransportError('Client is not connected.', message)

        pending_message = None
        if message.response_id:
            pending_message = PendingMessage(self._client)
            self._pending_messages[message.response_id] = pending_message

        try:
            await self._client.send_str(message.serialize())
            response = None
            if pending_message is not None:
                response = await pending_message.wait(self._timeout)
                if pending_message.connection_lost:
                    raise TransportError(
                        'Connection closed before a response was received',
                        message)
            return message.parse_response(response)
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', message, exc)
        finally:
            if pending_message is not None:
                del self._pending_messages[message.response_id]

    async def ws_connect(self, **kwargs):
        """Connect to the websocket server.

        Keyword arguments are passed on to aiohttp's ws_connect(), on top of
        the ones given to the constructor, and win over those. Headers are
        merged the same way, case-insensitively; leaving them out or passing
        None keeps the constructor headers. A timeout given here is
        aiohttp's websocket timeout, while the timeout given to the
        constructor is how long to wait for a response.
        """
        if self.connected:
            raise TransportError('Connection already open.')

        headers = CIMultiDict(self._connect_kwargs['headers'])
        headers.update(kwargs.pop('headers', None) or {})
        connect_kwargs = {
            **self._connect_kwargs, **kwargs, 'headers': headers}

        try:
            if self._internal_session and (
                    self._session is None or self._session.closed):
                self._session = aiohttp.ClientSession()
            client = await self._session.ws_connect(
                self._url, **connect_kwargs)
        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Error connecting to server', None, exc)
        self._client = client
        return asyncio.get_running_loop().create_task(self._ws_loop(client))

    async def _ws_loop(self, client):
        """Listen for messages from the websocket server."""
        msg = None
        try:
            async for msg in client:
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
                    # Handle method call in a task to prevent blocking the read
                    # loop
                    asyncio.get_running_loop().create_task(
                        self._receive_request(request))
                else:
                    pending_message = self._pending_messages.get(data['id'])
                    if pending_message is not None:
                        pending_message.response = data

        except (ClientError, HttpProcessingError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', None, exc)
        finally:
            # No responses can arrive for this client anymore
            self._fail_pending_messages(client)
            if self._client is client:
                await self.close()
            else:
                # close() already detached this client, so only finish
                # closing it here; self.close() would also tear down a
                # connection (and internal session) opened since then
                await client.close()
            if msg and msg.type == aiohttp.WSMsgType.ERROR:
                raise TransportError(
                    'Websocket error detected. Connection closed.')

    async def close(self):
        """Close the connection to the websocket server."""
        client = self._client
        self._client = None
        session = None
        if self._internal_session:
            # Detach the session too, so a ws_connect() made while this
            # close() is still running opens a new one
            session = self._session
            self._session = None
        try:
            if client is not None:
                # The reader of this client may never have started, so don't
                # rely on it to release the pending messages
                self._fail_pending_messages(client)
                await client.close()
        finally:
            if session is not None:
                await session.close()

    def _fail_pending_messages(self, client):
        """Release the calls still waiting for a response on client."""
        for pending_message in list(self._pending_messages.values()):
            if pending_message.client is client:
                pending_message.fail_connection_lost()

    @property
    def connected(self):
        """Websocket server is connected."""
        return self._client is not None

    async def _receive_request(self, request: jsonrpc_base.Request):
        """Handle request and log errors"""
        try:
            response = await self.async_receive_request(request)
            if response:
                await self.send_message(response)
        except Exception as exc:
            _LOGGER.exception('Error while handling request', exc_info=exc)


class PendingMessage(object):
    """Wait for response of pending message."""

    def __init__(self, client=None):
        self.client = client
        self.connection_lost = False
        self._event = asyncio.Event()
        self._response = None

    async def wait(self, timeout=None):
        async with async_timeout(timeout):
            await self._event.wait()
            return self._response

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value
        self._event.set()

    def fail_connection_lost(self):
        """Stop waiting, the connection closed before the response came."""
        if not self._event.is_set():
            self.connection_lost = True
            self._event.set()
