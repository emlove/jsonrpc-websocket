from __future__ import print_function

try:
    from setuptools import setup
except ImportError:
    import sys
    print("Please install the `setuptools` package in order to install this library", file=sys.stderr)
    raise

setup(
    name='jsonrpc-websocket',
    version='3.1.2',
    author='Emily Love Mills',
    author_email='emily@emlove.me',
    packages=('jsonrpc_websocket',),
    license='BSD',
    keywords='json-rpc async asyncio websocket',
    url='http://github.com/emlove/jsonrpc-websocket',
    description='''A JSON-RPC websocket client library for asyncio''',
    long_description_content_type='text/x-rst',
    long_description=open('README.rst').read(),
    install_requires=[
        'jsonrpc-base>=2.1.0',
        'aiohttp>=3.0.0',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],

)
