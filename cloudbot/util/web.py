"""
web.py

Contains functions for interacting with web services.

Created by:
    - Bjorn Neergaard <https://github.com/neersighted>

Maintainer:
    - Luke Rogers <https://github.com/lukeroge>

License:
    GPL v3
"""

import json

import requests
# Constants
from requests import RequestException

DEFAULT_SHORTENER = 'is.gd'
DEFAULT_PASTEBIN = 'snoonet'

HASTEBIN_SERVER = 'https://hastebin.com'

SNOONET_PASTE = 'https://paste.snoonet.org'


# Shortening / pasting

# Public API


def shorten(url, custom=None, key=None, service=DEFAULT_SHORTENER):
    impl = shorteners[service]
    return impl.shorten(url, custom, key)


def try_shorten(url, custom=None, key=None, service=DEFAULT_SHORTENER):
    impl = shorteners[service]
    return impl.try_shorten(url, custom, key)


def expand(url, service=None):
    impl = None
    if service:
        impl = shorteners[service]
    else:
        for name in shorteners:
            if name in url:
                impl = shorteners[name]
                break

    if impl:
        try:
            return impl.expand(url)
        except:
            pass

    impl = Shortener()
    return impl.expand(url)


def paste(data, ext='txt', service=DEFAULT_PASTEBIN):
    impl = pastebins[service]
    return impl.paste(data, ext)


class ServiceError(Exception):
    def __init__(self, message, request):
        super().__init__()
        self.message = message
        self.request = request

    def __str__(self):
        return '[HTTP {}] {}'.format(self.request.status_code, self.message)


class Shortener:
    def __init__(self):
        pass

    def shorten(self, url, custom=None, key=None):
        return url

    def try_shorten(self, url, custom=None, key=None):
        try:
            return self.shorten(url, custom, key)
        except ServiceError:
            return url

    def expand(self, url):
        try:
            r = requests.get(url, allow_redirects=False)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        if 'location' in r.headers:
            return r.headers['location']
        else:
            raise ServiceError('That URL does not redirect.', r)


class Pastebin:
    def __init__(self):
        pass

    def paste(self, data, ext):
        raise NotImplementedError


# Internal Implementations

shorteners = {}
pastebins = {}


def _shortener(name):
    def _decorate(impl):
        shorteners[name] = impl()

    return _decorate


def _pastebin(name):
    def _decorate(impl):
        pastebins[name] = impl()

    return _decorate


@_shortener('is.gd')
class Isgd(Shortener):
    def shorten(self, url, custom=None, key=None):
        p = {'url': url, 'shorturl': custom, 'format': 'json'}
        try:
            r = requests.get('https://is.gd/create.php', params=p)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        j = r.json()

        if 'shorturl' in j:
            return j['shorturl']
        else:
            raise ServiceError(j['errormessage'], r)

    def expand(self, url):
        p = {'shorturl': url, 'format': 'json'}
        try:
            r = requests.get('https://is.gd/forward.php', params=p)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        j = r.json()

        if 'url' in j:
            return j['url']
        else:
            raise ServiceError(j['errormessage'], r)


@_shortener('goo.gl')
class Googl(Shortener):
    def shorten(self, url, custom=None, key=None):
        h = {'content-type': 'application/json'}
        k = {'key': key}
        p = {'longUrl': url}
        try:
            r = requests.post('https://www.googleapis.com/urlshortener/v1/url', params=k, data=json.dumps(p), headers=h)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        j = r.json()

        if 'error' not in j:
            return j['id']
        else:
            raise ServiceError(j['error']['message'], r)

    def expand(self, url, key=None):
        p = {'shortUrl': url, 'key': key}
        try:
            r = requests.get('https://www.googleapis.com/urlshortener/v1/url', params=p)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        j = r.json()

        if 'error' not in j:
            return j['longUrl']
        else:
            raise ServiceError(j['error']['message'], r)


@_shortener('git.io')
class Gitio(Shortener):
    def shorten(self, url, custom=None, key=None):
        p = {'url': url, 'code': custom}
        try:
            r = requests.post('https://git.io', data=p)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)

        if r.status_code == requests.codes.created:
            s = r.headers['location']
            if custom and custom not in s:
                raise ServiceError('That URL is already in use', r)
            else:
                return s
        else:
            raise ServiceError(r.text, r)


@_pastebin('hastebin')
class Hastebin(Pastebin):
    def paste(self, data, ext):
        try:
            r = requests.post(HASTEBIN_SERVER + '/documents', data=data)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)
        else:
            j = r.json()

            if r.status_code is requests.codes.ok:
                return '{}/{}.{}'.format(HASTEBIN_SERVER, j['key'], ext)
            else:
                raise ServiceError(j['message'], r)



@_pastebin('snoonet')
class SnoonetPaste(Pastebin):
    def paste(self, data, ext):
        params = {
            'text': data,
            'expire': '1d'
        }
        try:
            r = requests.post(SNOONET_PASTE + '/paste/new', data=params)
            r.raise_for_status()
        except RequestException as e:
            r = e.response
            raise ServiceError(r.status_code, r)
        else:
            return '{}'.format(r.url)
