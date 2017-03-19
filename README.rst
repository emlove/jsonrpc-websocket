jsonrpc-websocket: a compact JSON-RPC websocket client library for asyncio
=======================================================================================================

.. image:: https://travis-ci.org/armills/jsonrpc-websocket.svg
    :target: https://travis-ci.org/armills/jsonrpc-websocket
.. image:: https://coveralls.io/repos/armills/jsonrpc-websocket/badge.svg
    :target: https://coveralls.io/r/armills/jsonrpc-websocket

This is a compact and simple JSON-RPC websocket client implementation for asyncio python code. This code is forked from https://github.com/gciotta/jsonrpc-requests

Main Features
-------------

* Python 3.4 & 3.5 compatible
* Supports nested namespaces (eg. `app.users.getUsers()`)
* 100% test coverage

Usage
-----
It is recommended to manage the aiohttp ClientSession object externally and pass it to the Server constructor. `(See the aiohttp documentation.) <https://aiohttp.readthedocs.io/en/stable/client_reference.html#aiohttp.ClientSession>`_ If not passed to Server, a ClientSession object will be created automatically.

Execute remote JSON-RPC functions

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    @asyncio.coroutine
    def routine():
        server = Server('ws://localhost:9090')
        try:
            yield from server.ws_connect()

            yield from server.foo(1, 2)
            yield from server.foo(bar=1, baz=2)
            yield from server.foo({'foo': 'bar'})
            yield from server.foo.bar(baz=1, qux=2)
        finally:
            yield from server.close()
            yield from server.session.close()

    asyncio.get_event_loop().run_until_complete(routine())

A notification

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    @asyncio.coroutine
    def routine():
        server = Server('ws://localhost:9090')
        try:
            yield from server.ws_connect()

            yield from server.foo(bar=1, _notification=True)
        finally:
            yield from server.close()
            yield from server.session.close()

    asyncio.get_event_loop().run_until_complete(routine())

Handle requests from server to client

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    def client_method(arg1, arg2):
        return arg1 + arg2

    @asyncio.coroutine
    def routine():
        server = Server('ws://localhost:9090')
        # client_method is called when server requests method 'namespace.client_method'
        server.namespace.client_method = client_method
        try:
            yield from server.ws_connect()
        finally:
            yield from server.close()
            yield from server.session.close()

    asyncio.get_event_loop().run_until_complete(routine())

Pass through arguments to aiohttp (see also `aiohttp  documentation <http://aiohttp.readthedocs.io/en/stable/client_reference.html#aiohttp.ClientSession.request>`_)

.. code-block:: python

    import asyncio
    import aiohttp
    from jsonrpc_websocket import Server

    @asyncio.coroutine
    def routine():
        server = Server(
            'ws://localhost:9090',
            auth=aiohttp.BasicAuth('user', 'pass'),
            headers={'x-test2': 'true'})
        try:
            yield from server.ws_connect()

            yield from server.foo()
        finally:
            yield from server.close()
            yield from server.session.close()

    asyncio.get_event_loop().run_until_complete(routine())

Pass through aiohttp exceptions

.. code-block:: python

    import asyncio
    import aiohttp
    from jsonrpc_websocket import Server

    @asyncio.coroutine
    def routine():
        server = Server('ws://unknown-host')
        try:
            yield from server.ws_connect()

            yield from server.foo()
        except TransportError as transport_error:
            print(transport_error.args[1]) # this will hold a aiohttp exception instance
        finally:
            yield from server.close()
            yield from server.session.close()

    asyncio.get_event_loop().run_until_complete(routine())

Tests
-----
Install the Python tox package and run ``tox``, it'll test this package with various versions of Python.

Credits
-------
`@gciotta <https://github.com/gciotta>`_ for creating the base project `jsonrpc-requests <https://github.com/gciotta/jsonrpc-requests>`_.

`@mbroadst <https://github.com/mbroadst>`_ for providing full support for nested method calls, JSON-RPC RFC
compliance and other improvements.

`@vaab <https://github.com/vaab>`_ for providing api and tests improvements, better RFC compliance.
