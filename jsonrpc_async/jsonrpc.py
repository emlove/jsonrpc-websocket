import asyncio
import functools

import aiohttp
import jsonrpc_base
from jsonrpc_base import JSONRPCError, TransportError, ProtocolError


class Server(jsonrpc_base.Server):
    """A connection to a HTTP JSON-RPC server, backed by aiohttp"""

    def __init__(self, url, session=None, **post_kwargs):
        super().__init__()
        session = session or aiohttp.ClientSession()
        post_kwargs['headers'] = post_kwargs.get('headers', {})
        post_kwargs['headers']['Content-Type'] = post_kwargs['headers'].get(
            'Content-Type', 'application/json')
        post_kwargs['headers']['Accept'] = post_kwargs['headers'].get(
            'Accept', 'application/json-rpc')
        self._request = functools.partial(session.post, url, **post_kwargs)

    @asyncio.coroutine
    def send_message(self, message):
        """Send the HTTP message to the server and return the message response.

        No result is returned if message is a notification.
        """
        try:
            response = yield from self._request(data=message.serialize())
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise TransportError('Transport Error', message, exc)

        try:
            if response.status != 200:
                raise TransportError('HTTP %d %s' % (response.status, response.reason), message)

            try:
                response_text = yield from response.text()
            except ValueError as value_error:
                raise TransportError('Cannot deserialize response body', message, value_error)

            return message.parse_response(response_text)
        finally:
            yield from response.release()
