import random
import sys
import json
import functools

import requests


class JSONRPCError(Exception):
    """Root exception for all errors related to this library"""


class TransportError(JSONRPCError):
    """An error occurred while performing a connection to the server"""


class ProtocolError(JSONRPCError):
    """An error occurred while dealing with the JSON-RPC protocol"""


class Server(object):
    """A connection to a HTTP JSON-RPC server, backed by requests"""
    def __init__(self, url, **requests_kwargs):
        self.request = functools.partial(requests.post, url, **requests_kwargs)
        self.method_name = None  # the RPC method name we're going to call

    def send_request(self, method_name, is_notification, params):
        """Issue the HTTP request to the server and return the method result (if not a notification)"""
        request_body = self.serialize(method_name, params, is_notification)
        try:
            response = self.request(data=request_body)
        except requests.RequestException as requests_exception:
            raise TransportError('Error calling method %s' % method_name, requests_exception)

        if not response.status_code == requests.codes.ok:
            raise TransportError(response.status_code)

        if not is_notification:
            try:
                return self.parse_result(response.json())
            except ValueError as value_error:
                raise TransportError('Cannot deserialize response body', value_error)

    @staticmethod
    def parse_result(result):
        """Parse the data returned by the server according to the JSON-RPC spec. Try to be liberal in what we accept."""
        if not isinstance(result, dict):
            raise ProtocolError('Response is not a dictionary')
        if result.get('error'):
            code = result['error'].get('code', '')
            message = result['error'].get('message', '')
            raise ProtocolError(code, message)
        elif not 'result' in result:
            raise ProtocolError('Response without a result field')
        else:
            return result['result']

    @staticmethod
    def dumps(data):
        """Override this method to customize the serialization process (eg. datetime handling)"""
        return json.dumps(data)

    def serialize(self, method_name, params, is_notification):
        """Generate the raw JSON message to be sent to the server"""
        data = {'jsonrpc': '2.0', 'method': method_name}
        if params:
            data['params'] = params
        if not is_notification:
            # some JSON-RPC servers complain when receiving str(uuid.uuid4()). Let's pick something simpler.
            data['id'] = random.randint(1, sys.maxsize)
        return self.dumps(data)

    def __getattr__(self, method_name):
        """Allow calling a method accessing server.method_name()"""
        if self.method_name:  # accessing a second-level namespace, like server.utils.something()
            self.method_name = '%s.%s' % (self.method_name, method_name)
        else:
            self.method_name = method_name
        return self

    def __call__(self, *args, **kwargs):
        """Perform the actual RPC call. If _notification=True, send a notification and don't wait for a response"""
        is_notification = kwargs.pop('_notification', False)
        if args and kwargs:
            raise ProtocolError('JSON-RPC spec forbids mixing arguments and keyword arguments')
        method_name = self.method_name
        self.method_name = None  # clear it so that we don't continue nesting namespaces in __getattr__
        return self.send_request(method_name, is_notification, args or kwargs)
