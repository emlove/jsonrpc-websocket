import asyncio
import functools

import aiohttp
import jsonrpc_base
from jsonrpc_base import JSONRPCError, TransportError, ProtocolError


class Server(jsonrpc_base.Server):
    """A connection to a HTTP JSON-RPC server, backed by aiohttp"""

    def __init__(self, url, session=None, **post_kwargs):
        self.session = session or aiohttp.ClientSession()
        post_kwargs['headers'] = post_kwargs.get('headers', {})
        post_kwargs['headers']['Content-Type'] = post_kwargs['headers'].get('Content-Type', 'application/json')
        post_kwargs['headers']['Accept'] = post_kwargs['headers'].get('Accept', 'application/json-rpc')
        self.request = functools.partial(self.session.post, url, **post_kwargs)

    @asyncio.coroutine
    def send_request(self, method_name, is_notification, params):
        """Issue the HTTP request to the server and return the method result (if not a notification)"""
        request_body = self.serialize(method_name, params, is_notification)
        try:
            response = yield from self.request(data=request_body)
        except (aiohttp.ClientResponseError, aiohttp.ClientOSError) as exc:
            raise TransportError('Error calling method %r' % method_name, exc)

        try:
            if response.status != 200:
                raise TransportError('HTTP %d %s' % (response.status, response.reason))

            if not is_notification:
                try:
                    parsed = yield from response.json()
                except ValueError as value_error:
                    raise TransportError('Cannot deserialize response body', value_error)

                return self.parse_result(parsed)
        finally:
            yield from response.release()
