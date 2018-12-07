"""
This file contains various utility methods.
"""
import sys
from collections import namedtuple


def is_python3():
    return sys.version_info.major > 2


if sys.version_info.major > 2:
    import configparser
    from configparser import DuplicateSectionError, MissingSectionHeaderError, NoSectionError, ParsingError, \
        DEFAULTSECT, RawConfigParser
    from http.client import HTTP_PORT
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from io import StringIO
    import socketserver
    from urllib.parse import parse_qsl, unquote_plus, urlsplit, urlparse
    from urllib.request import url2pathname
    grange = range
    is_long_or_int = lambda x: isinstance(x, int)
    cast_to_unicode = lambda x: "".join([chr(c) for c in x]) if isinstance(x, bytes) else str(x)
else:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    import ConfigParser as configparser
    from ConfigParser import DuplicateSectionError, MissingSectionHeaderError, NoSectionError, ParsingError, \
        DEFAULTSECT, RawConfigParser
    from httplib import HTTP_PORT
    import SocketServer as socketserver
    from StringIO import StringIO
    from urllib import unquote_plus, url2pathname
    from urlparse import parse_qsl, urlsplit, urlparse
    grange = xrange
    is_long_or_int = lambda x: isinstance(x, (int, long))
    cast_to_unicode = lambda x: unicode(x)
StringIO = StringIO
socketserver = socketserver
configparser = configparser

configparser_future = namedtuple('configparser_future', ['DuplicateSectionError', 'MissingSectionHeaderError',
                                                         'NoSectionError', 'ParsingError', 'DEFAULTSECT',
                                                         'RawConfigParser'])\
    (DuplicateSectionError, MissingSectionHeaderError, NoSectionError, ParsingError, DEFAULTSECT, RawConfigParser)
urllib_future = namedtuple('urllib_future', ['urlsplit', 'parse_qsl', 'urlparse', 'unquote_plus', 'url2pathname'])\
    (urlsplit, parse_qsl, urlparse, unquote_plus, url2pathname)
httplib_future = namedtuple('httplib_future', ['HTTP_PORT'])(HTTP_PORT)
httpserver_future = namedtuple('httpserver_future', ['BaseHTTPRequestHandler', 'HTTPServer'])\
    (BaseHTTPRequestHandler, HTTPServer)
