import asyncio
import inspect
import json
import os
import random
import unittest
from unittest.mock import Mock

import aiohttp
import aiohttp.web
from aiohttp.test_utils import unittest_run_loop, setup_test_loop, teardown_test_loop
import pep8

import jsonrpc_base
import jsonrpc_websocket.jsonrpc
from jsonrpc_websocket import Server, ProtocolError, TransportError


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

class JsonTestServer():
    def __init__(self, loop=None):
        self.loop = loop
        self.send_handler = None
        self.receive_queue = asyncio.Queue(loop=loop)
        self._closed = False
        self.receive_side_effect = None

    async def send_str(self, data):
        self.send_handler(self, data)

    def test_receive(self, data):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, data, ''))

    def test_binary(self, data=bytes()):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, data, ''))

    def test_error(self):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.ERROR, 0, ''))

    def test_close(self):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, 0, ''))

    def test_ping(self):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.PING, 0, ''))

    async def receive(self):
        value = await self.receive_queue.get()
        if self.receive_side_effect:
            self.receive_side_effect()
        return (value)

    async def close(self):
        if not self._closed:
            self._closed = True
            self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, 0, ''))

class TestCase(unittest.TestCase):
    def assertSameJSON(self, json1, json2):
        """Tells whether two json strings, once decoded, are the same dictionary"""
        return self.assertDictEqual(json.loads(json1), json.loads(json2))

    def assertRaisesRegex(self, *args, **kwargs):
        return super(TestCase, self).assertRaisesRegex(*args, **kwargs)


class TestJSONRPCClient(TestCase):

    def setUp(self):
        self.loop = setup_test_loop()
        self.client = JsonTestClient(self.loop)
        random.randint = Mock(return_value=1)
        self.server = Server('/xmlrpc', session=self.client, timeout=0.2)
        self.ws_loop_future = self.loop.run_until_complete(self.server.ws_connect())

    def tearDown(self):
        if self.server.connected:
            self.client.test_server.test_close()
            self.loop.run_until_complete(self.ws_loop_future)
        teardown_test_loop(self.loop)

    @property
    def handler(self):
        return self.client.test_server.send_handler

    @handler.setter
    def handler(self, value):
        self.client.test_server.send_handler = value

    def receive(self, data):
        self.client.test_server.test_receive(data)

    def receive_binary(self, data):
        self.client.test_server.test_binary(data)

    def test_pep8_conformance(self):
        """Test that we conform to PEP8."""

        source_files = []
        project_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.join(project_dir, 'jsonrpc_async')
        for root, directories, filenames in os.walk(package_dir):
            source_files.extend([os.path.join(root, f) for f in filenames if f.endswith('.py')])

        pep8style = pep8.StyleGuide(quiet=False, max_line_length=120)
        result = pep8style.check_files(source_files)
        self.assertEqual(result.total_errors, 0, "Found code style errors (and warnings).")

    def test_pending_message_response(self):
        pending_message = jsonrpc_websocket.jsonrpc.PendingMessage(loop=self.loop)
        pending_message.response = 10
        self.assertEqual(pending_message.response, 10)

    @unittest_run_loop
    async def test_send_message(self):
        # catch timeout responses
        with self.assertRaises(TransportError) as transport_error:
            def handler(server, data):
                try:
                    asyncio.wait(asyncio.sleep(10, loop=self.loop))
                except asyncio.CancelledError:
                    # event loop will be terminated before sleep finishes
                    pass

            self.handler = handler
            await self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

        self.assertIsInstance(transport_error.exception.args[1], asyncio.TimeoutError)

    @unittest_run_loop
    async def test_client_closed(self):
        await self.server.close()
        with self.assertRaisesRegex(TransportError, 'Client is not connected.'):
            def handler(server, data):
                pass
            self.handler = handler
            await self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

    @unittest_run_loop
    async def test_double_connect(self):
        with self.assertRaisesRegex(TransportError, 'Connection already open.'):
            await self.server.ws_connect()

    @unittest_run_loop
    async def test_ws_error(self):
        self.client.test_server.test_error()
        with self.assertRaisesRegex(TransportError, 'Websocket error detected. Connection closed.'):
            await self.ws_loop_future

    @unittest_run_loop
    async def test_binary(self):
        self.client.test_server.test_binary()

    @unittest_run_loop
    async def test_message_not_json(self):
        with self.assertRaises(TransportError) as transport_error:
            self.receive('not json')
            await self.ws_loop_future
        self.assertIsInstance(transport_error.exception.args[1], ValueError)

    @unittest_run_loop
    async def test_message_binary_not_utf8(self):
        # If we get a binary message, we should try to decode it as JSON, but
        # if it's not valid we should just ignore it, and an exception should
        # not be thrown
        self.receive_binary(bytes((0xE0, 0x80, 0x80)))
        self.client.test_server.test_close()
        await self.ws_loop_future

    @unittest_run_loop
    async def test_message_binary_not_json(self):
        # If we get a binary message, we should try to decode it as JSON, but
        # if it's not valid we should just ignore it, and an exception should
        # not be thrown
        self.receive_binary('not json'.encode())
        self.client.test_server.test_close()
        await self.ws_loop_future

    @unittest_run_loop
    async def test_message_ping_ignored(self):
        self.client.test_server.test_ping()
        self.client.test_server.test_close()
        await self.ws_loop_future

    @unittest_run_loop
    async def test_connection_timeout(self):
        def bad_connect():
            raise aiohttp.ClientError("Test Error")
        self.client.connect_side_effect = bad_connect
        await self.server.close()
        with self.assertRaises(TransportError) as transport_error:
            await self.server.ws_connect()
        self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientError)

    @unittest_run_loop
    async def test_server_request(self):
        def test_method():
            return 1
        self.server.test_method = test_method

        def handler(server, data):
            response = json.loads(data)
            self.assertEqual(response["result"], 1)
        self.handler = handler

        self.receive('{"jsonrpc": "2.0", "method": "test_method", "id": 1}')

    @unittest_run_loop
    async def test_server_request_binary(self):
        # Test that if the server sends a binary websocket message, that's a
        # UTF-8 encoded JSON request we process it
        def test_method():
            return 1
        self.server.test_method = test_method

        def handler(server, data):
            response = json.loads(data)
            self.assertEqual(response["result"], 1)

        self.handler = handler

        self.receive_binary('{"jsonrpc": "2.0", "method": "test_method", "id": 1}'.encode())

    @unittest_run_loop
    async def test_server_notification(self):
        def test_method():
            pass
        self.server.test_method = test_method
        self.receive('{"jsonrpc": "2.0", "method": "test_method"}')

    @unittest_run_loop
    async def test_server_response_error(self):
        def test_method():
            return 1
        self.server.test_method = test_method

        def receive_side_effect():
            raise aiohttp.ClientError("Test Error")
        self.client.test_server.receive_side_effect = receive_side_effect
        self.receive('{"jsonrpc": "2.0", "method": "test_method", "id": 1}')

        with self.assertRaises(TransportError) as transport_error:
            await self.ws_loop_future
        self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientError)

    @unittest_run_loop
    async def test_calls(self):
        # rpc call with positional parameters:
        def handler1(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], [42, 23])
            server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

        self.handler = handler1
        self.assertEqual((await self.server.subtract(42, 23)), 19)

        def handler2(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], {'y': 23, 'x': 42})
            server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

        self.handler = handler2
        self.assertEqual((await self.server.subtract(x=42, y=23)), 19)

        def handler3(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], {'foo': 'bar'})

        self.handler = handler3
        await self.server.foobar({'foo': 'bar'}, _notification=True)

    @unittest_run_loop
    async def test_simultaneous_calls(self):
        # Test that calls can be delivered simultaneously, and can return out
        # of order
        def handler(server, data):
            pass

        self.handler = handler

        random.randint = Mock(return_value=1)
        task1 = self.loop.create_task(self.server.call1())
        random.randint = Mock(return_value=2)
        task2 = self.loop.create_task(self.server.call2())

        self.assertFalse(task1.done())
        self.assertFalse(task2.done())

        self.receive('{"jsonrpc": "2.0", "result": 2, "id": 2}')
        await task2

        self.assertFalse(task1.done())
        self.assertTrue(task2.done())

        self.receive('{"jsonrpc": "2.0", "result": 1, "id": 1}')
        await task1

        self.assertTrue(task1.done())
        self.assertTrue(task2.done())

        self.assertEqual(1, task1.result())
        self.assertEqual(2, task2.result())

    @unittest_run_loop
    async def test_notification(self):
        # Verify that we ignore the server response
        def handler(server, data):
            pass
        self.handler = handler
        self.assertIsNone((await self.server.subtract(42, 23, _notification=True)))


if __name__ == '__main__':
    unittest.main()
