from __future__ import print_function

try:
    from setuptools import setup
except ImportError:
    import sys
    print("Please install the `setuptools` package in order to install this library", file=sys.stderr)
    raise

setup(
    name='jsonrpc-websocket',
    version='1.0.0',
    author='Adam Mills',
    author_email='adam@armills.info',
    packages=('jsonrpc_websocket',),
    license='BSD',
    keywords='json-rpc async asyncio websocket',
    url='http://github.com/armills/jsonrpc-websocket',
    description='''A JSON-RPC websocket client library for asyncio''',
    long_description=open('README.rst').read(),
    install_requires=[
        'jsonrpc-base>=1.0.1',
        'aiohttp>=3.0.0',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

)
