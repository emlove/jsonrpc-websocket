jsonrpc-async: a compact JSON-RPC client library for asyncio
=======================================================================================================

.. image:: https://travis-ci.org/armills/jsonrpc-async.svg
    :target: https://travis-ci.org/armills/jsonrpc-async
.. image:: https://coveralls.io/repos/armills/jsonrpc-async/badge.svg
    :target: https://coveralls.io/r/armills/jsonrpc-async

This is a compact and simple JSON-RPC client implementation for asyncio python code. This code is forked from https://github.com/gciotta/jsonrpc-async

Main Features
-------------

* Python 3.4 & 3.5 compatible
* Supports nested namespaces (eg. `app.users.getUsers()`)
* 100% test coverage

Usage
-----
TODO
.. code-block:: python

    from jsonrpc_requests import Server
    server = Server('http://localhost:8080')
    server.foo(1, 2)
    server.foo(bar=1, baz=2)
    server.foo({'foo': 'bar'})
    server.foo.bar(baz=1, qux=2)

A notification:

.. code-block:: python

    from jsonrpc_requests import Server
    server.foo(bar=1, _notification=True)

Pass through arguments to requests (see also `requests  documentation <http://docs.python-requests.org/en/latest/>`_)

.. code-block:: python

    from jsonrpc_requests import Server
    server = Server('http://localhost:8080', auth=('user', 'pass'), headers={'x-test2': 'true'})

Pass through requests exceptions

.. code-block:: python

    from jsonrpc_requests import Server, TransportError
    server = Server('http://unknown-host')
    try:
        server.foo()
    except TransportError as transport_error:
        print(transport_error.args[1]) # this will hold a `requests.exceptions.RequestException` instance


Tests
-----
Install the Python tox package and run ``tox``, it'll test this package with various versions of Python.

Credits
-------
`@gciotta <https://github.com/gciotta>`_ for creating the base project `jsonrpc-requests <https://github.com/gciotta/jsonrpc-requests>`_.
`@mbroadst <https://github.com/mbroadst>`_ for providing full support for nested method calls, JSON-RPC RFC
compliance and other improvements.

`@vaab <https://github.com/vaab>`_ for providing api and tests improvements, better RFC compliance.
