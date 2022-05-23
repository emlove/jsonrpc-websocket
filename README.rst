jsonrpc-websocket: a compact JSON-RPC websocket client library for asyncio
=======================================================================================================

.. image:: https://img.shields.io/pypi/v/jsonrpc-websocket.svg
        :target: https://pypi.python.org/pypi/jsonrpc-websocket
.. image:: https://github.com/emlove/jsonrpc-websocket/workflows/tests/badge.svg
        :target: https://github.com/emlove/jsonrpc-websocket/actions
.. image:: https://coveralls.io/repos/emlove/jsonrpc-websocket/badge.svg?branch=main
    :target: https://coveralls.io/github/emlove/jsonrpc-websocket?branch=main

This is a compact and simple JSON-RPC websocket client implementation for asyncio python code. This code is forked from https://github.com/gciotta/jsonrpc-requests

Main Features
-------------

* Supports nested namespaces (eg. `app.users.getUsers()`)
* 100% test coverage

Usage
-----
It is recommended to manage the aiohttp ClientSession object externally and pass it to the Server constructor. `(See the aiohttp documentation.) <https://aiohttp.readthedocs.io/en/stable/client_reference.html#aiohttp.ClientSession>`_ If not passed to Server, a ClientSession object will be created automatically, and will be closed when the websocket connection is closed. If you pass in an external ClientSession, it is your responsibility to close it when you are finished.

Execute remote JSON-RPC functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    async def routine():
        server = Server('ws://localhost:9090')
        try:
            await server.ws_connect()

            await server.foo(1, 2)
            await server.foo(bar=1, baz=2)
            await server.foo({'foo': 'bar'})
            await server.foo.bar(baz=1, qux=2)
        finally:
            await server.close()

    asyncio.get_event_loop().run_until_complete(routine())

A notification
~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    async def routine():
        server = Server('ws://localhost:9090')
        try:
            await server.ws_connect()

            await server.foo(bar=1, _notification=True)
        finally:
            await server.close()

    asyncio.get_event_loop().run_until_complete(routine())

Handle requests from server to client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    from jsonrpc_websocket import Server

    def client_method(arg1, arg2):
        return arg1 + arg2

    async def routine():
        server = Server('ws://localhost:9090')
        # client_method is called when server requests method 'namespace.client_method'
        server.namespace.client_method = client_method
        try:
            await server.ws_connect()
        finally:
            await server.close()

    asyncio.get_event_loop().run_until_complete(routine())

Pass through arguments to aiohttp (see also `aiohttp  documentation <http://aiohttp.readthedocs.io/en/stable/client_reference.html#aiohttp.ClientSession.request>`_)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiohttp
    from jsonrpc_websocket import Server

    async def routine():
        server = Server(
            'ws://localhost:9090',
            auth=aiohttp.BasicAuth('user', 'pass'),
            headers={'x-test2': 'true'})
        try:
            await server.ws_connect()

            await server.foo()
        finally:
            await server.close()

    asyncio.get_event_loop().run_until_complete(routine())

Pass through aiohttp exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiohttp
    from jsonrpc_websocket import Server

    async def routine():
        server = Server('ws://unknown-host')
        try:
            await server.ws_connect()

            await server.foo()
        except TransportError as transport_error:
            print(transport_error.args[1]) # this will hold a aiohttp exception instance
        finally:
            await server.close()

    asyncio.get_event_loop().run_until_complete(routine())

Tests
-----
Install the Python tox package and run ``tox``, it'll test this package with various versions of Python.

Changelog
---------
3.1.4 (2022-05-23)
~~~~~~~~~~~~~~~~~~
- Only reconnect session when the session is managed internally
- Remove deprecated with timeout syntax

3.1.3 (2022-05-23)
~~~~~~~~~~~~~~~~~~
- Fix unclosed client session bug `(#12) <https://github.com/emlove/jsonrpc-websocket/pull/12>`_ `@Arjentix <https://github.com/Arjentix>`_

3.1.2 (2022-05-03)
~~~~~~~~~~~~~~~~~~
- Unpin test dependencies

3.1.1 (2021-11-21)
~~~~~~~~~~~~~~~~~~
- Fixed compatibility with async_timeout 4.0

3.1.0 (2021-05-03)
~~~~~~~~~~~~~~~~~~
- Bumped jsonrpc-base to version 2.1.0

3.0.0 (2021-03-17)
~~~~~~~~~~~~~~~~~~
- Bumped jsonrpc-base to version 2.0.0
- BREAKING CHANGE: `Allow single mapping as a positional parameter. <https://github.com/emlove/jsonrpc-base/pull/6>`_
  Previously, when calling with a single dict as a parameter (example: ``server.foo({'bar': 0})``), the mapping was used as the JSON-RPC keyword parameters. This made it impossible to send a mapping as the first and only positional parameter. If you depended on the old behavior, you can recreate it by spreading the mapping as your method's kwargs. (example: ``server.foo(**{'bar': 0})``)

2.0.0 (2020-12-22)
~~~~~~~~~~~~~~~~~~
- Remove session as a reserved attribute on Server

1.2.1 (2020-09-11)
~~~~~~~~~~~~~~~~~~
- Fix loop not closing after client closes

1.2.0 (2020-08-24)
~~~~~~~~~~~~~~~~~~
- Support for async server request handlers

1.1.0 (2020-02-17)
~~~~~~~~~~~~~~~~~~
- Support servers that send JSON-RPC requests as binary messages encoded with UTF-8 `(#5) <https://github.com/emlove/jsonrpc-websocket/pull/5>`_ `@shiaky <https://github.com/shiaky>`_

1.0.2 (2019-11-12)
~~~~~~~~~~~~~~~~~~
- Bumped jsonrpc-base to version 1.0.3

1.0.1 (2018-08-23)
~~~~~~~~~~~~~~~~~~
- Bumped jsonrpc-base to version 1.0.2

1.0.0 (2018-07-06)
~~~~~~~~~~~~~~~~~~
- Bumped jsonrpc-base to version 1.0.1

0.6 (2018-03-11)
~~~~~~~~~~~~~~~~
- Minimum required version of aiohttp is now 3.0.
- Support for Python 3.4 is now dropped.

Credits
-------
`@gciotta <https://github.com/gciotta>`_ for creating the base project `jsonrpc-requests <https://github.com/gciotta/jsonrpc-requests>`_.

`@mbroadst <https://github.com/mbroadst>`_ for providing full support for nested method calls, JSON-RPC RFC
compliance and other improvements.

`@vaab <https://github.com/vaab>`_ for providing api and tests improvements, better RFC compliance.
