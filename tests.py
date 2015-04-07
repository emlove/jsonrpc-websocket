import unittest
import random
import json
import inspect
import os

import pep8
import requests
import requests.exceptions
import responses

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
        """Verify that this library is really smaller than 100 lines, as stated in README.rst"""
        with open(inspect.getfile(Server)) as library_file:
            self.assertLessEqual(len([l for l in library_file.readlines()
                                      if l.strip()]), 100)

    def test_pep8_conformance(self):
        """Test that we conform to PEP8."""

        source_files = []
        project_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.join(project_dir, 'jsonrpc_requests')
        for root, directories, filenames in os.walk(package_dir):
            source_files.extend([os.path.join(root, f) for f in filenames if f.endswith('.py')])

        pep8style = pep8.StyleGuide(quiet=False, max_line_length=120)
        result = pep8style.check_files(source_files)
        self.assertEqual(result.total_errors, 0, "Found code style errors (and warnings).")

    def test_dumps(self):
        # test keyword args
        self.assertSameJSON(
            '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": "1"}''',
            self.server.serialize('my_method_name', params={'foo': 'bar'}, is_notification=False)
        )
        # test positional args
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": "1"}''',
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

    @responses.activate
    def test_send_request(self):
        # catch non-json responses
        with self.assertRaises(TransportError) as transport_error:
            responses.add(responses.POST, 'http://mock/xmlrpc', body='not json', content_type='application/json')
            self.server.send_request('my_method', is_notification=False, params=None)

        self.assertEqual(transport_error.exception.args[0], 'Cannot deserialize response body')
        self.assertIsInstance(transport_error.exception.args[1], ValueError)
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

    def test_exception_passthrough(self):
        with self.assertRaises(TransportError) as transport_error:
            s = Server('http://host-doesnt-exist')
            s.foo()
        self.assertEqual(transport_error.exception.args[0], 'Error calling method foo')
        self.assertIsInstance(transport_error.exception.args[1], requests.exceptions.RequestException)

    def test_forbid_private_methods(self):
        """Test that we can't call private class methods (those starting with '_')"""
        s = Server('http://host-doesnt-exist')
        with self.assertRaises(AttributeError):
            s._foo()

        # nested private method call
        with self.assertRaises(AttributeError):
            s.foo.bar._baz()

    @responses.activate
    def test_headers_passthrough(self):
        """Test that we correctly send RFC-defined headers and merge them with user defined ones"""
        def callback(request):
            expected_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json-rpc',
                'X-TestCustomHeader': '1'
            }
            self.assertTrue(set(expected_headers.items()).issubset(set(request.headers.items())))
            return 200, {}, u'{"jsonrpc": "2.0", "result": true, "id": 1}'

        responses.add_callback(
            responses.POST, 'http://mock/xmlrpc', content_type='application/json', callback=callback,
        )
        s = Server('http://mock/xmlrpc', headers={'X-TestCustomHeader': '1'})
        s.foo()

    def test_method_call(self):
        """mixing *args and **kwargs is forbidden by the spec"""
        with self.assertRaisesRegex(ProtocolError, 'JSON-RPC spec forbids mixing arguments and keyword arguments'):
            self.server.testmethod(1, 2, a=1, b=2)

    @responses.activate
    def test_method_nesting(self):
        """Test that we correctly nest namespaces"""
        def callback(request):
            request_message = json.loads(request.body)
            if (request_message["params"][0] == request_message["method"]):
                return (200, {}, u'{"jsonrpc": "2.0", "result": true, "id": 1}')
            else:
                return (200, {}, u'{"jsonrpc": "2.0", "result": false, "id": 1}')

        responses.add_callback(
            responses.POST, 'http://mock/xmlrpc', content_type='application/json', callback=callback,
        )

        self.assertEqual(self.server.nest.testmethod("nest.testmethod"), True)
        self.assertEqual(self.server.nest.testmethod.some.other.method("nest.testmethod.some.other.method"), True)

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
