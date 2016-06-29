jsonrpc-requests: a compact JSON-RPC client library backed by `requests  <http://python-requests.org>`_
=======================================================================================================

.. image:: https://travis-ci.org/gciotta/jsonrpc-requests.svg
    :target: https://travis-ci.org/gciotta/jsonrpc-requests
.. image:: https://coveralls.io/repos/gciotta/jsonrpc-requests/badge.svg
    :target: https://coveralls.io/r/gciotta/jsonrpc-requests

This is a compact (~100 SLOC) and simple JSON-RPC client implementation written while debugging a picky server.

Main Features
-------------

* Python 2.7, 3.4 & 3.5 compatible
* Exposes requests options
* Supports nested namespaces (eg. `app.users.getUsers()`)
* 100% test coverage

TODO
----

* Batch requests (http://www.jsonrpc.org/specification#batch)

Usage
-----
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
`@mbroadst <https://github.com/mbroadst>`_ for providing full support for nested method calls, JSON-RPC RFC
compliance and other improvements.

`@vaab <https://github.com/vaab>`_ for providing api and tests improvements, better RFC compliance.
