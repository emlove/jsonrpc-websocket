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

from jsonrpc_async import Server, ProtocolError, TransportError

try:
    # python 3.3
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

class JsonTestClient(aiohttp.test_utils.TestClient):
    def __init__(self, app_or_server):
        super().__init__(app_or_server)
        self.request_callback = None

    def request(self, method, path, *args, **kwargs):
        if callable(self.request_callback):
            self.request_callback(method, path, *args, **kwargs)
        return super().request(method, path, *args, **kwargs)

class TestCase(unittest.TestCase):
    def assertSameJSON(self, json1, json2):
        """Tells whether two json strings, once decoded, are the same dictionary"""
        return self.assertDictEqual(json.loads(json1), json.loads(json2))

    def assertRaisesRegex(self, *args, **kwargs):
        return super(TestCase, self).assertRaisesRegex(*args, **kwargs)


class TestJSONRPCClient(TestCase):

    def setUp(self):
        self.loop = setup_test_loop()
        self.app = self.get_app(self.loop)

        @asyncio.coroutine
        def create_client(app):
            return JsonTestClient(app)

        self.client = self.loop.run_until_complete(create_client(self.app))
        self.loop.run_until_complete(self.client.start_server())
        random.randint = Mock(return_value=1)
        self.server = Server('/xmlrpc', session=self.client)

    def tearDown(self):
        self.loop.run_until_complete(self.client.close())
        teardown_test_loop(self.loop)

    def get_app(self, loop):
        @asyncio.coroutine
        def response_func(request):
            return (yield from self.handler(request))
        app = aiohttp.web.Application(loop=loop)
        app.router.add_post('/xmlrpc', response_func)
        return app

    def test_length(self):
        """Verify that this library is really smaller than 100 lines, as stated in README.rst"""
        with open(inspect.getfile(Server)) as library_file:
            self.assertLessEqual(len([l for l in library_file.readlines()
                                      if l.strip()]), 100)

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

    def test_dumps(self):
        # test keyword args
        self.assertSameJSON(
            '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            self.server.serialize('my_method_name', params={'foo': 'bar'}, is_notification=False)
        )
        # test positional args
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            self.server.serialize('my_method_name', params=('foo', 'bar'), is_notification=False)
        )
        # test notification
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name"}''',
            self.server.serialize('my_method_name', params=('foo', 'bar'), is_notification=True)
        )

    def test_parse_result(self):
        with self.assertRaisesRegex(ProtocolError, 'Response is not a dictionary'):
            self.server.parse_result([])
        with self.assertRaisesRegex(ProtocolError, 'Response without a result field'):
            self.server.parse_result({})
        with self.assertRaises(ProtocolError) as protoerror:
            body = {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
            self.server.parse_result(body)
        self.assertEqual(protoerror.exception.args[0], -32601)
        self.assertEqual(protoerror.exception.args[1], 'Method not found')

    @unittest_run_loop
    @asyncio.coroutine
    def test_send_request(self):
        # catch non-json responses
        with self.assertRaises(TransportError) as transport_error:
            @asyncio.coroutine
            def handler(request):
                return aiohttp.web.Response(text='not json', content_type='application/json')

            self.handler = handler
            yield from self.server.send_request('my_method', is_notification=False, params=None)

        self.assertEqual(transport_error.exception.args[0], 'Cannot deserialize response body')
        self.assertIsInstance(transport_error.exception.args[1], ValueError)

        # catch non-200 responses
        with self.assertRaisesRegex(TransportError, '404'):
            @asyncio.coroutine
            def handler(request):
                return aiohttp.web.Response(text='{}', content_type='application/json', status=404)

            self.handler = handler
            yield from self.server.send_request('my_method', is_notification=False, params=None)

        # a notification
        @asyncio.coroutine
        def handler(request):
            return aiohttp.web.Response(text='we dont care about this', content_type='application/json')

        self.handler = handler
        yield from self.server.send_request('my_notification', is_notification=True, params=None)

        # catch aiohttp own exception
        with self.assertRaisesRegex(TransportError, 'aiohttp exception'):
            def callback(method, path, *args, **kwargs):
                raise aiohttp.ClientResponseError('aiohttp exception')
            self.client.request_callback = callback
            yield from self.server.send_request('my_method', is_notification=False, params=None)

    @unittest_run_loop
    @asyncio.coroutine
    def test_exception_passthrough(self):
        with self.assertRaises(TransportError) as transport_error:
            def callback(method, path, *args, **kwargs):
                raise aiohttp.ClientOSError('aiohttp exception')
            self.client.request_callback = callback
            yield from self.server.foo()
        self.assertEqual(transport_error.exception.args[0], "Error calling method 'foo'")
        self.assertIsInstance(transport_error.exception.args[1], aiohttp.ClientOSError)

    @unittest_run_loop
    @asyncio.coroutine
    def test_forbid_private_methods(self):
        """Test that we can't call private class methods (those starting with '_')"""
        with self.assertRaises(AttributeError):
            yield from self.server._foo()

        # nested private method call
        with self.assertRaises(AttributeError):
            yield from self.server.foo.bar._baz()

    @unittest_run_loop
    @asyncio.coroutine
    def test_headers_passthrough(self):
        """Test that we correctly send RFC-defined headers and merge them with user defined ones"""
        @asyncio.coroutine
        def handler(request):
            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": true, "id": 1}', content_type='application/json')

        self.handler = handler
        def callback(method, path, *args, **kwargs):
            expected_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json-rpc',
                'X-TestCustomHeader': '1'
            }
            self.assertTrue(set(expected_headers.items()).issubset(set(kwargs['headers'].items())))

        self.client.request_callback = callback
        s = Server('/xmlrpc', session=self.client, headers={'X-TestCustomHeader': '1'})
        yield from s.foo()

    @unittest_run_loop
    @asyncio.coroutine
    def test_method_call(self):
        """mixing *args and **kwargs is forbidden by the spec"""
        with self.assertRaisesRegex(ProtocolError, 'JSON-RPC spec forbids mixing arguments and keyword arguments'):
            yield from self.server.testmethod(1, 2, a=1, b=2)

    @unittest_run_loop
    @asyncio.coroutine
    def test_method_nesting(self):
        """Test that we correctly nest namespaces"""
        @asyncio.coroutine
        def handler(request):
            request_message = yield from request.json()
            if (request_message["params"][0] == request_message["method"]):
                return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": true, "id": 1}', content_type='application/json')
            else:
                return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": false, "id": 1}', content_type='application/json')

        self.handler = handler

        self.assertEqual((yield from self.server.nest.testmethod("nest.testmethod")), True)
        self.assertEqual((yield from self.server.nest.testmethod.some.other.method("nest.testmethod.some.other.method")), True)

    @unittest_run_loop
    @asyncio.coroutine
    def test_calls(self):
        # rpc call with positional parameters:
        @asyncio.coroutine
        def handler1(request):
            request_message = yield from request.json()
            self.assertEqual(request_message["params"], [42, 23])
            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": 19, "id": 1}', content_type='application/json')

        self.handler = handler1
        self.assertEqual((yield from self.server.subtract(42, 23)), 19)

        @asyncio.coroutine
        def handler2(request):
            request_message = yield from request.json()
            self.assertEqual(request_message["params"], {'y': 23, 'x': 42})
            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": 19, "id": 1}', content_type='application/json')

        self.handler = handler2
        self.assertEqual((yield from self.server.subtract(x=42, y=23)), 19)

        @asyncio.coroutine
        def handler3(request):
            request_message = yield from request.json()
            self.assertEqual(request_message["params"], {'foo': 'bar'})
            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": null}', content_type='application/json')

        self.handler = handler3
        yield from self.server.foobar({'foo': 'bar'})

    @unittest_run_loop
    @asyncio.coroutine
    def test_notification(self):
        # Verify that we ignore the server response
        @asyncio.coroutine
        def handler(request):
            return aiohttp.web.Response(text='{"jsonrpc": "2.0", "result": 19, "id": 1}', content_type='application/json')

        self.handler = handler
        self.assertIsNone((yield from self.server.subtract(42, 23, _notification=True)))


if __name__ == '__main__':
    unittest.main()
