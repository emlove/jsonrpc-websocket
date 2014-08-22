from setuptools import setup

setup(
    name='jsonrpc-requests',
    version='0.1',
    author='Giuseppe Ciotta',
    author_email='gciotta@gmail.com',
    packages=('jsonrpc_requests',),
    license='BSD',
    keywords='json-rpc requests',
    url='http://github.com/gciotta/jsonrpc-requests',
    description='''A JSON-RPC client library, backed by requests''',
    long_description=open('README.rst').read(),
    install_requires=('requests',),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],

)
