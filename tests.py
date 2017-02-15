import asyncio
import unittest
import random
import json
import inspect
import os

import aiohttp
import aiohttp.web
from aiohttp.test_utils import TestClient, unittest_run_loop, setup_test_loop, teardown_test_loop
import pep8

import jsonrpc_base
import jsonrpc_websocket.jsonrpc
from jsonrpc_websocket import Server, ProtocolError, TransportError

try:
    # python 3.3
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

class JsonTestClient():
    def __init__(self, loop=None):
        self.test_server = None
        self.loop = loop
        self.connect_side_effect = None

    @asyncio.coroutine
    def ws_connect(self, *args, **kwargs):
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

    def send_str(self, data):
        self.send_handler(self, data)

    def test_receive(self, data):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, data, ''))

    def test_binary(self):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, 0, ''))

    def test_error(self):
        self.receive_queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.ERROR, 0, ''))

    @asyncio.coroutine
    def receive(self):
        value = yield from self.receive_queue.get()
        if self.receive_side_effect:
            self.receive_side_effect()
        return (value)

    @asyncio.coroutine
    def close(self):
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
        self.loop.run_until_complete(self.server.ws_connect())
        self.loop.create_task(self.server.ws_loop())

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        teardown_test_loop(self.loop)

    @property
    def handler(self):
        return self.client.test_server.send_handler

    @handler.setter
    def handler(self, value):
        self.client.test_server.send_handler = value

    def receive(self, data):
        self.client.test_server.test_receive(data)

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
    @asyncio.coroutine
    def test_send_message(self):
        # catch timeout responses
        with self.assertRaises(TransportError) as transport_error:
            def handler(server, data):
                try:
                    asyncio.wait(asyncio.sleep(10, loop=self.loop))
                except asyncio.CancelledError:
                    # event loop will be terminated before sleep finishes
                    pass

            self.handler = handler
            yield from self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

        self.assertIsInstance(transport_error.exception.args[1], asyncio.TimeoutError)

    @unittest_run_loop
    @asyncio.coroutine
    def test_client_closed(self):
        yield from self.server.close()
        with self.assertRaisesRegex(TransportError, 'Client is not connected.'):
            def handler(server, data):
                pass
            self.handler = handler
            yield from self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

    @unittest_run_loop
    @asyncio.coroutine
    def test_double_connect(self):
        with self.assertRaisesRegex(TransportError, 'Connection already open.'):
            yield from self.server.ws_connect()

    @unittest_run_loop
    @asyncio.coroutine
    def test_ws_error(self):
        yield from self.server.close()
        yield from self.server.ws_connect()
        with self.assertRaisesRegex(TransportError, 'Websocket error detected. Connection closed.'):
            self.client.test_server.test_error()
            yield from self.server.ws_loop()

    @unittest_run_loop
    @asyncio.coroutine
    def test_binary(self):
        self.client.test_server.test_binary()

    @unittest_run_loop
    @asyncio.coroutine
    def test_message_not_json(self):
        yield from self.server.close()
        yield from self.server.ws_connect()
        with self.assertRaises(TransportError) as transport_error:
            self.receive('not json')
            yield from self.server.ws_loop()
        self.assertIsInstance(transport_error.exception.args[1], ValueError)

    @unittest_run_loop
    @asyncio.coroutine
    def test_connection_timeout(self):
        def bad_connect():
            raise aiohttp.ClientError("Test Error")
        self.client.connect_side_effect = bad_connect
        yield from self.server.close()
        with self.assertRaises(TransportError) as transport_error:
            yield from self.server.ws_connect()
        self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientError)

    @unittest_run_loop
    @asyncio.coroutine
    def test_server_request(self):
        def test_method():
            return 1
        self.server.test_method = test_method

        def handler(server, data):
            response = json.loads(data)
            self.assertEqual(response["result"], 1)
        self.handler = handler

        self.receive('{"jsonrpc": "2.0", "method": "test_method", "id": 1}')

    @unittest_run_loop
    @asyncio.coroutine
    def test_server_notification(self):
        def test_method():
            pass
        self.server.test_method = test_method
        self.receive('{"jsonrpc": "2.0", "method": "test_method"}')

    @unittest_run_loop
    @asyncio.coroutine
    def test_server_response_error(self):
        yield from self.server.close()
        yield from self.server.ws_connect()
        def test_method():
            return 1
        self.server.test_method = test_method

        def receive_side_effect():
            raise aiohttp.ClientError("Test Error")
        self.client.test_server.receive_side_effect = receive_side_effect
        self.receive('{"jsonrpc": "2.0", "method": "test_method", "id": 1}')

        with self.assertRaises(TransportError) as transport_error:
            yield from self.server.ws_loop()
        self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientError)

    #    # catch non-json responses
    #    with self.assertRaises(TransportError) as transport_error:
    #        def handler(server, data):
    #            server.test_receive('not json')

    #        self.handler = handler
    #        yield from self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

    #    self.assertEqual(transport_error.exception.args[0], "Error calling method 'my_method': Transport Error")
    #    self.assertIsInstance(transport_error.exception.args[1], ValueError)

    #    # catch non-200 responses
    #    with self.assertRaisesRegex(TransportError, '404'):
    #        @asyncio.coroutine
    #        def handler(request):
    #            return aiohttp.web.Response(text='{}', content_type='application/json', status=404)

    #        self.handler = handler
    #        yield from self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

    #    # a notification
    #    @asyncio.coroutine
    #    def handler(request):
    #        return aiohttp.web.Response(text='we dont care about this', content_type='application/json')

    #    self.handler = handler
    #    yield from self.server.send_message(jsonrpc_base.Request('my_notification', params=None))

    #    # catch aiohttp own exception
    #    with self.assertRaisesRegex(TransportError, 'aiohttp exception'):
    #        def callback(method, path, *args, **kwargs):
    #            raise aiohttp.ClientResponseError('aiohttp exception')
    #        self.client.request_callback = callback
    #        yield from self.server.send_message(jsonrpc_base.Request('my_method', params=None, msg_id=1))

    #@unittest_run_loop
    #@asyncio.coroutine
    #def test_exception_passthrough(self):
    #    with self.assertRaises(TransportError) as transport_error:
    #        def callback(method, path, *args, **kwargs):
    #            raise aiohttp.ClientOSError('aiohttp exception')
    #        self.client.request_callback = callback
    #        yield from self.server.foo()
    #    self.assertEqual(transport_error.exception.args[0], "Error calling method 'foo': Transport Error")
    #    self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientOSError)

    #@unittest_run_loop
    #@asyncio.coroutine
    #def test_forbid_private_methods(self):
    #    """Test that we can't call private class methods (those starting with '_')"""
    #    with self.assertRaises(AttributeError):
    #        yield from self.server._foo()

    #    # nested private method call
    #    with self.assertRaises(AttributeError):
    #        yield from self.server.foo.bar._baz()

    #@unittest_run_loop
    #@asyncio.coroutine
    #def test_headers_passthrough(self):
    #    """Test that we correctly send RFC-defined headers and merge them with user defined ones"""
    #    @asyncio.coroutine
    #    def handler(request):
    #        return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": true, "id": 1}', content_type='application/json')

    #    self.handler = handler
    #    def callback(method, path, *args, **kwargs):
    #        expected_headers = {
    #            'Content-Type': 'application/json',
    #            'Accept': 'application/json-rpc',
    #            'X-TestCustomHeader': '1'
    #        }
    #        self.assertTrue(set(expected_headers.items()).issubset(set(kwargs['headers'].items())))

    #    self.client.request_callback = callback
    #    s = Server('/xmlrpc', session=self.client, headers={'X-TestCustomHeader': '1'})
    #    self.loop.create_task(s.ws_loop())
    #    yield from s.foo()
    #    yield from s.close()

    #@unittest_run_loop
    #@asyncio.coroutine
    #def test_method_call(self):
    #    """mixing *args and **kwargs is forbidden by the spec"""
    #    with self.assertRaisesRegex(ProtocolError, 'JSON-RPC spec forbids mixing arguments and keyword arguments'):
    #        yield from self.server.testmethod(1, 2, a=1, b=2)

    #@unittest_run_loop
    #@asyncio.coroutine
    #def test_method_nesting(self):
    #    """Test that we correctly nest namespaces"""
    #    @asyncio.coroutine
    #    def handler(request):
    #        request_message = yield from request.json()
    #        if (request_message["params"][0] == request_message["method"]):
    #            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": true, "id": 1}', content_type='application/json')
    #        else:
    #            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": false, "id": 1}', content_type='application/json')

    #    self.handler = handler

    #    self.assertEqual((yield from self.server.nest.testmethod("nest.testmethod")), True)
    #    self.assertEqual((yield from self.server.nest.testmethod.some.other.method("nest.testmethod.some.other.method")), True)

    @unittest_run_loop
    @asyncio.coroutine
    def test_calls(self):
        # rpc call with positional parameters:
        def handler1(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], [42, 23])
            server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

        self.handler = handler1
        self.assertEqual((yield from self.server.subtract(42, 23)), 19)

        def handler2(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], {'y': 23, 'x': 42})
            server.test_receive('{"jsonrpc": "2.0", "result": 19, "id": 1}')

        self.handler = handler2
        self.assertEqual((yield from self.server.subtract(x=42, y=23)), 19)

        def handler3(server, data):
            request = json.loads(data)
            self.assertEqual(request["params"], {'foo': 'bar'})

        self.handler = handler3
        yield from self.server.foobar({'foo': 'bar'}, _notification=True)

    @unittest_run_loop
    @asyncio.coroutine
    def test_notification(self):
        # Verify that we ignore the server response
        def handler(server, data):
            pass
        self.handler = handler
        self.assertIsNone((yield from self.server.subtract(42, 23, _notification=True)))


if __name__ == '__main__':
    unittest.main()
