import unittest
import random
import json
import requests
import responses
import inspect

from jsonrpc_requests import Server, ProtocolError, TransportError

try:
    # python 3.3
    from unittest.mock import Mock
except ImportError:
    from mock import Mock


class TestCase(unittest.TestCase):
    def assertSameJSON(self, json1, json2):
        """Tells whether two json strings, once decoded, are the same dictionary"""
        return self.assertDictEqual(json.loads(json1), json.loads(json2))

    def assertRaisesRegex(self, *args, **kwargs):
        if hasattr(super(TestCase, self), 'assertRaisesRegex'):
            # python 3.3
            return super(TestCase, self).assertRaisesRegex(*args, **kwargs)
        else:
            # python 2.7
            return self.assertRaisesRegexp(*args, **kwargs)


class TestJSONRPCClient(TestCase):

    def setUp(self):
        random.randint = Mock(return_value="1")
        self.server = Server('http://mock/xmlrpc')

    def test_length(self):
        """Verify that this library is really smaller than 90 lines, as stated in README.rst"""
        with open(inspect.getfile(Server)) as library_file:
            self.assertLessEqual(len(library_file.readlines()), 90)

    def test_dumps(self):
        # test keyword args
        self.assertSameJSON(
            '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": "1"}''',
            self.server.dumps('my_method_name', params={'foo': 'bar'}, is_notification=False)
        )
        # test positional args
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": "1"}''',
            self.server.dumps('my_method_name', params=('foo', 'bar'), is_notification=False)
        )
        # test notification
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name"}''',
            self.server.dumps('my_method_name', params=('foo', 'bar'), is_notification=True)
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

    @responses.activate
    def test_send_request(self):
        # catch non-json responses
        with self.assertRaisesRegex(TransportError, 'Cannot deserialize response body'):
            responses.add(responses.POST, 'http://mock/xmlrpc', body='not json', content_type='application/json')
            self.server.send_request('my_method', is_notification=False, params=None)
        responses.reset()

        # catch non-200 responses
        with self.assertRaisesRegex(TransportError, '404'):
            responses.add(responses.POST, 'http://mock/xmlrpc', body='{}', content_type='application/json', status=404)
            self.server.send_request('my_method', is_notification=False, params=None)
        responses.reset()

        # catch requests own exception
        with self.assertRaisesRegex(TransportError, 'Requests exception'):
            def callback(request):
                raise requests.RequestException('Requests exception')
            responses.add_callback(
                responses.POST, 'http://mock/xmlrpc', content_type='application/json', callback=callback,
            )
            self.server.send_request('my_method', is_notification=False, params=None)
        responses.reset()

        # a notification
        responses.add(responses.POST, 'http://mock/xmlrpc', body='we dont care about this',
                      content_type='application/json')
        self.server.send_request('my_notification', is_notification=True, params=None)
        responses.reset()

    def test_method_call(self):
        """mixing *args and **kwargs is forbidden by the spec"""
        with self.assertRaisesRegex(ProtocolError, 'JSON-RPC spec forbids mixing arguments and keyword arguments'):
            self.server.testmethod(1, 2, a=1, b=2)

    def test_method_nesting(self):
        """Test that we correctly nest namespaces"""
        nested_method = self.server.nest.testmethod
        self.assertEqual(nested_method.method_name, 'nest.testmethod')

    @responses.activate
    def test_calls(self):
        # rpc call with positional parameters:
        responses.add(responses.POST, 'http://mock/xmlrpc',
                      body='{"jsonrpc": "2.0", "result": 19, "id": 1}',
                      content_type='application/json')
        self.assertEqual(self.server.subtract(42, 23), 19)
        responses.reset()

        # rpc call with named parameters
        responses.add(responses.POST, 'http://mock/xmlrpc',
                      body='{"jsonrpc": "2.0", "result": 19, "id": 3}',
                      content_type='application/json')
        self.assertEqual(self.server.subtract(42, 23), 19)
        responses.reset()

    @responses.activate
    def test_notification(self):
        # Verify that we ignore the server response
        responses.add(responses.POST, 'http://mock/xmlrpc',
                      body='{"jsonrpc": "2.0", "result": 19, "id": 3}',
                      content_type='application/json')
        self.assertIsNone(self.server.subtract(42, 23, _notification=True))
        responses.reset()


if __name__ == '__main__':
    unittest.main()
