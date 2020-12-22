import asyncio
import json
import random
from unittest.mock import Mock
from asynctest import MagicMock, patch

import aiohttp
from aiohttp import ClientWebSocketResponse
import aiohttp.web
import pytest

import jsonrpc_base
import jsonrpc_websocket.jsonrpc
from jsonrpc_websocket import Server, TransportError

pytestmark = pytest.mark.asyncio


class JsonTestClient():
    def __init__(self, loop=None):
        self.test_server = None
        self.loop = loop
        self.connect_side_effect = None

    async def ws_connect(self, *args, **kwargs):
        if self.connect_side_effect:
            self.connect_side_effect()
        self.test_server = JsonTestServer(self.loop)
        return self.test_server

    @property
    def handler(self):
        return self.test_server.send_handler

    @handler.setter
    def handler(self, value):
        self.test_server.send_handler = value

    def receive(self, data):
        self.test_server.test_receive(data)

    def receive_binary(self, data):
        self.test_server.test_binary(data)


class JsonTestServer(ClientWebSocketResponse):
    def __init__(self, loop=None):
        self.loop = loop
        self.send_handler = None
        self.receive_queue = asyncio.Queue()
        self._closed = False
        self.receive_side_effect = None

    async def send_str(self, data):
        self.send_handler(self, data)

    def test_receive(self, data):
        self.receive_queue.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, data, ''))

    def test_binary(self, data=bytes()):
        self.receive_queue.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, data, ''))

    def test_error(self):
        self.receive_queue.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.ERROR, 0, ''))

    def test_close(self):
        self.receive_queue.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, None, None))

    def test_ping(self):
        self.receive_queue.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.PING, 0, ''))

    async def receive(self):
        value = await self.receive_queue.get()
        if self.receive_side_effect:
            self.receive_side_effect()
        return (value)

    async def close(self):
        if not self._closed:
            self._closed = True
            self.receive_queue.put_nowait(
                aiohttp.WSMessage(aiohttp.WSMsgType.CLOSING, None, None))


def assertSameJSON(json1, json2):
    """Tells whether two json strings, once decoded, are the same dictionary"""
    assert json.loads(json1) == json.loads(json2)


@pytest.fixture(autouse=True)
def mock_rand():
    """Mock the build in rand method for determinism in tests."""
    random.randint = Mock(return_value=1)


@pytest.fixture()
async def server(event_loop):
    """Generate a mock json server."""
    client = JsonTestClient(event_loop)
    server = Server('/xmlrpc', session=client, timeout=0.2)
    client.run_loop_future = await server.ws_connect()
    yield server
    if server.connected:
        client.test_server.test_close()
        await client.run_loop_future


def test_pending_message_response():
    pending_message = jsonrpc_websocket.jsonrpc.PendingMessage()
    pending_message.response = 10
    assert pending_message.response == 10


async def test_internal_session():
    client = MagicMock(spec=aiohttp.ClientSession)
    with patch('jsonrpc_websocket.jsonrpc.aiohttp.ClientSession',
               return_value=client) as client_class:
        server = Server('/xmlrpc', timeout=0.2)
        client_class.assert_called_once()

        await server.close()

        client.close.assert_called_once()


async def test_send_message(server):
    # catch timeout responses
    with pytest.raises(TransportError) as transport_error:
        def handler(server, data):
            try:
                sleep_coroutine = asyncio.sleep(10)
                wait_coroutine = asyncio.wait(sleep_coroutine)
            except asyncio.CancelledError:
                # event loop will be terminated before sleep finishes
                pass

            # Prevent warning about non-awaited coroutines
            sleep_coroutine.close()
            wait_coroutine.close()

        server._session.handler = handler
        await server.send_message(
            jsonrpc_base.Request('my_method', params=None, msg_id=1))

    assert isinstance(transport_error.value.args[1], asyncio.TimeoutError)


async def test_client_closed(server):
    assert server._session.run_loop_future.done() is False
    await server.close()
    assert server._session.run_loop_future.done() is False
    await server._session.run_loop_future
    assert server._session.run_loop_future.done() is True
    with pytest.raises(TransportError, match='Client is not connected.'):
        def handler(server, data):
            pass
        server._session.handler = handler
        await server.send_message(
            jsonrpc_base.Request('my_method', params=None, msg_id=1))


async def test_double_connect(server):
    with pytest.raises(TransportError, match='Connection already open.'):
        await server.ws_connect()


async def test_ws_error(server):
    server._session.test_server.test_error()
    with pytest.raises(
            TransportError,
            match='Websocket error detected. Connection closed.'):
        await server._session.run_loop_future


async def test_binary(server):
    server._session.test_server.test_binary()


async def test_message_not_json(server):
    with pytest.raises(TransportError) as transport_error:
        server._session.receive('not json')
        await server._session.run_loop_future
    assert isinstance(transport_error.value.args[1], ValueError)


async def test_message_binary_not_utf8(server):
    # If we get a binary message, we should try to decode it as JSON, but
    # if it's not valid we should just ignore it, and an exception should
    # not be thrown
    server._session.receive_binary(bytes((0xE0, 0x80, 0x80)))
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_message_binary_not_json(server):
    # If we get a binary message, we should try to decode it as JSON, but
    # if it's not valid we should just ignore it, and an exception should
    # not be thrown
    server._session.receive_binary('not json'.encode())
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_message_ping_ignored(server):
    server._session.test_server.test_ping()
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_connection_timeout(server):
    def bad_connect():
        raise aiohttp.ClientError("Test Error")
    server._session.connect_side_effect = bad_connect
    await server.close()
    with pytest.raises(TransportError) as transport_error:
        await server.ws_connect()
    assert isinstance(transport_error.value.args[1], aiohttp.ClientError)


async def test_server_request(server):
    def test_method():
        return 1
    server.test_method = test_method

    def handler(server, data):
        response = json.loads(data)
        assert response["result"] == 1

    server._session.handler = handler

    server._session.receive(
        '{"jsonrpc": "2.0", "method": "test_method", "id": 1}')
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_server_async_request(server):
    async def test_method_async():
        return 2
    server.test_method_async = test_method_async

    def handler(server, data):
        response = json.loads(data)
        assert response["result"] == 2
    server._session.handler = handler

    server._session.receive(
        '{"jsonrpc": "2.0", "method": "test_method_async", "id": 1}')
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_server_request_binary(server):
    # Test that if the server sends a binary websocket message, that's a
    # UTF-8 encoded JSON request we process it
    def test_method_binary():
        return 1
    server.test_method_binary = test_method_binary

    def handler(server, data):
        response = json.loads(data)
        assert response["result"] == 1

    server._session.handler = handler

    server._session.receive_binary(
        '{"jsonrpc": "2.0", "method": "test_method_binary", "id": 1}'.encode())
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_server_notification(server):
    def test_notification():
        pass
    server.test_notification = test_notification
    server._session.receive(
        '{"jsonrpc": "2.0", "method": "test_notification"}')
    server._session.test_server.test_close()
    await server._session.run_loop_future


async def test_server_response_error(server):
    def test_error():
        return 1
    server.test_error = test_error

    def receive_side_effect():
        raise aiohttp.ClientError("Test Error")
    server._session.test_server.receive_side_effect = receive_side_effect
    server._session.receive(
        '{"jsonrpc": "2.0", "method": "test_error", "id": 1}')
    server._session.test_server.test_close()

    with pytest.raises(TransportError) as transport_error:
        await server._session.run_loop_future
    assert isinstance(transport_error.value.args[1], aiohttp.ClientError)


async def test_calls(server):
    # rpc call with positional parameters:
    def handler1(server, data):
        request = json.loads(data)
        assert request["params"] == [42, 23]
        server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

    server._session.handler = handler1
    assert (await server.subtract(42, 23)) == 19

    def handler2(server, data):
        request = json.loads(data)
        assert request["params"] == {'y': 23, 'x': 42}
        server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

    server._session.handler = handler2
    assert (await server.subtract(x=42, y=23)) == 19

    def handler3(server, data):
        request = json.loads(data)
        assert request["params"] == {'foo': 'bar'}

    server._session.handler = handler3
    await server.foobar({'foo': 'bar'}, _notification=True)


async def test_simultaneous_calls(event_loop, server):
    # Test that calls can be delivered simultaneously, and can return out
    # of order
    def handler(server, data):
        pass

    server._session.handler = handler

    random.randint = Mock(return_value=1)
    task1 = event_loop.create_task(server.call1())
    random.randint = Mock(return_value=2)
    task2 = event_loop.create_task(server.call2())

    assert task1.done() is False
    assert task2.done() is False

    server._session.receive('{"jsonrpc": "2.0", "result": 2, "id": 2}')
    await task2

    assert task1.done() is False
    assert task2.done()

    server._session.receive('{"jsonrpc": "2.0", "result": 1, "id": 1}')
    await task1

    assert task1.done()
    assert task2.done()

    assert 1 == task1.result()
    assert 2 == task2.result()


async def test_notification(server):
    # Verify that we ignore the server response
    def handler(server, data):
        pass
    server._session.handler = handler
    assert (await server.subtract(42, 23, _notification=True)) is None
