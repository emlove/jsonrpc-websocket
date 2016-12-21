from __future__ import print_function

try:
    from setuptools import setup
except ImportError:
    import sys
    print("Please install the `setuptools` package in order to install this library", file=sys.stderr)
    raise

setup(
    name='jsonrpc-async',
    version='0.1',
    author='Adam Mills',
    author_email='adam@armills.info',
    packages=('jsonrpc_async',),
    license='BSD',
    keywords='json-rpc async asyncio',
    url='http://github.com/armills/jsonrpc-async',
    description='''A JSON-RPC client library for asyncio''',
    long_description=open('README.rst').read(),
    install_requires=[
        'jsonrpc-base==0.1',
        'aiohttp>=1.1.6',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

)
