# Copyright 2010, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# pylint: disable=protected-access,missing-docstring,too-few-public-methods,invalid-name,too-many-public-methods
from __future__ import absolute_import

import unittest
import socket

import httpplus

# relative import to ease embedding the library
from . import util


def make_preloaded_socket(data, close=False):
    """Make a socket pre-loaded with data so it can be read during connect.

    Useful for https proxy tests because we have to read from the
    socket during _connect rather than later on.
    """
    def preloaded_socket(*args, **kwargs):
        sock = util.MockSocket(*args, **kwargs)
        sock.early_data = data[:]
        sock.close_on_empty = close
        return sock
    return preloaded_socket


class ProxyHttpTest(util.HttpTestBase, unittest.TestCase):

    def _run_simple_test(self, host, server_data, expected_req, expected_data):
        con = httpplus.HTTPConnection(host)
        con._connect({})
        con.sock.data = server_data
        con.request('GET', '/')

        self.assertEqual(expected_req, con.sock.sent)
        self.assertEqual(expected_data, con.getresponse().read())

    def testSimpleRequest(self):
        con = httpplus.HTTPConnection('1.2.3.4:80',
                                  proxy_hostport=('magicproxy', 4242))
        con._connect({})
        con.sock.data = [b'HTTP/1.1 200 OK\r\n',
                         b'Server: BogusServer 1.0\r\n',
                         b'MultiHeader: Value\r\n'
                         b'MultiHeader: Other Value\r\n'
                         b'MultiHeader: One More!\r\n'
                         b'Content-Length: 10\r\n',
                         b'\r\n'
                         b'1234567890'
                         ]
        con.request('GET', '/')

        expected_req = (b'GET http://1.2.3.4/ HTTP/1.1\r\n'
                        b'Host: 1.2.3.4\r\n'
                        b'accept-encoding: identity\r\n\r\n')

        self.assertEqual((b'127.0.0.42', 4242), con.sock.sa)
        self.assertStringEqual(expected_req, con.sock.sent)
        resp = con.getresponse()
        self.assertEqual(b'1234567890', resp.read())
        self.assertEqual(['Value', 'Other Value', 'One More!'],
                         resp.headers.getheaders('multiheader'))
        self.assertEqual(['BogusServer 1.0'],
                         resp.headers.getheaders('server'))

    def testProxyHeadersNoHostPortRaises(self):
        self.assertRaises(ValueError, httpplus.HTTPConnection,
                          '1.2.3.4:443',
                          proxy_headers={'Proxy-Authorization': 'yes!'})

    def testSSLRequestProxyAuthInRequestHeaders(self):
        ph = {'Proxy-Authorization': 'hello'}
        con = httpplus.HTTPConnection('1.2.3.4:443',
                                      proxy_hostport=('magicproxy', 4242))
        socket.socket = make_preloaded_socket(
            [b'HTTP/1.1 200 OK\r\n',
             b'Server: BogusServer 1.0\r\n',
             b'Content-Length: 10\r\n',
             b'\r\n'
             b'1234567890'])
        con._connect(httpplus._foldheaders(ph))
        con.sock.data = [b'HTTP/1.1 200 OK\r\n',
                         b'Server: BogusServer 1.0\r\n',
                         b'Content-Length: 10\r\n',
                         b'\r\n'
                         b'1234567890'
                         ]
        connect_sent = con.sock.sent
        con.sock.sent = b''
        con.request('GET', '/', headers=ph)

        expected_connect = (b'CONNECT 1.2.3.4:443 HTTP/1.0\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'Proxy-Authorization: hello\r\n'
                            b'accept-encoding: identity\r\n'
                            b'\r\n')
        expected_request = (b'GET / HTTP/1.1\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'accept-encoding: identity\r\n\r\n')

        self.assertEqual((b'127.0.0.42', 4242), con.sock.sa)
        self.assertStringEqual(expected_connect, connect_sent)
        self.assertStringEqual(expected_request, con.sock.sent)
        resp = con.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(b'1234567890', resp.read())
        self.assertEqual(['BogusServer 1.0'],
                         resp.headers.getheaders('server'))

    def testSSLRequest(self):
        ph = {'Proxy-Authorization': 'this string is not meaningful'}
        con = httpplus.HTTPConnection('1.2.3.4:443',
                                      proxy_hostport=('magicproxy', 4242),
                                      proxy_headers=ph)
        socket.socket = make_preloaded_socket(
            [b'HTTP/1.1 200 OK\r\n',
             b'Server: BogusServer 1.0\r\n',
             b'Content-Length: 10\r\n',
             b'\r\n'
             b'1234567890'])
        con._connect(httpplus._foldheaders(ph))
        con.sock.data = [b'HTTP/1.1 200 OK\r\n',
                         b'Server: BogusServer 1.0\r\n',
                         b'Content-Length: 10\r\n',
                         b'\r\n'
                         b'1234567890'
                         ]
        connect_sent = con.sock.sent
        con.sock.sent = b''
        con.request('GET', '/')

        expected_connect = (b'CONNECT 1.2.3.4:443 HTTP/1.0\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'Proxy-Authorization: this string is '
                            b'not meaningful\r\n'
                            b'accept-encoding: identity\r\n'
                            b'\r\n')
        expected_request = (b'GET / HTTP/1.1\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'accept-encoding: identity\r\n\r\n')

        self.assertEqual((b'127.0.0.42', 4242), con.sock.sa)
        self.assertStringEqual(expected_connect, connect_sent)
        self.assertStringEqual(expected_request, con.sock.sent)
        resp = con.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(b'1234567890', resp.read())
        self.assertEqual(['BogusServer 1.0'],
                         resp.headers.getheaders('server'))

    def testSSLRequestNoConnectBody(self):
        con = httpplus.HTTPConnection('1.2.3.4:443',
                                  proxy_hostport=('magicproxy', 4242))
        socket.socket = make_preloaded_socket(
            [b'HTTP/1.1 200 OK\r\n',
             b'Server: BogusServer 1.0\r\n',
             b'\r\n'])
        con._connect({})
        con.sock.data = [b'HTTP/1.1 200 OK\r\n',
                         b'Server: BogusServer 1.0\r\n',
                         b'Content-Length: 10\r\n',
                         b'\r\n'
                         b'1234567890'
                         ]
        connect_sent = con.sock.sent
        con.sock.sent = b''
        con.request('GET', '/')

        expected_connect = (b'CONNECT 1.2.3.4:443 HTTP/1.0\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'accept-encoding: identity\r\n'
                            b'\r\n')
        expected_request = (b'GET / HTTP/1.1\r\n'
                            b'Host: 1.2.3.4\r\n'
                            b'accept-encoding: identity\r\n\r\n')

        self.assertEqual((b'127.0.0.42', 4242), con.sock.sa)
        self.assertStringEqual(expected_connect, connect_sent)
        self.assertStringEqual(expected_request, con.sock.sent)
        resp = con.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(b'1234567890', resp.read())
        self.assertEqual(['BogusServer 1.0'],
                         resp.headers.getheaders('server'))

    def testSSLProxyFailure(self):
        con = httpplus.HTTPConnection('1.2.3.4:443',
                                  proxy_hostport=('magicproxy', 4242))
        socket.socket = make_preloaded_socket(
            [b'HTTP/1.1 407 Proxy Authentication Required\r\n\r\n'], close=True)
        self.assertRaises(httpplus.HTTPProxyConnectFailedException,
                          con._connect, {})
        self.assertRaises(httpplus.HTTPProxyConnectFailedException,
                          con.request, 'GET', '/')
