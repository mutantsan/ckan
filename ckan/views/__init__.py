from __future__ import annotations

from typing import Any, Optional

from urllib.parse import quote
from flask.wrappers import Response

from ckan.common import g, request, config, current_user, logout_user
import ckan.plugins as p

import logging
log = logging.getLogger(__name__)


def set_cors_headers_for_response(response: Response) -> Response:
    '''
    Set up Access Control Allow headers if either origin_allow_all is True, or
    the request Origin is in the origin_whitelist.
    '''
    if request.headers.get('Origin'):
        cors_origin_allowed = None
        allow_all = config.get('ckan.cors.origin_allow_all')
        whitelisted = request.headers.get('Origin') in config.get(
            'ckan.cors.origin_whitelist')
        if allow_all:
            cors_origin_allowed = '*'
        elif whitelisted:
            # set var to the origin to allow it.
            cors_origin_allowed: str | None = request.headers.get('Origin')

        if cors_origin_allowed is not None:
            response.headers['Access-Control-Allow-Origin'] = \
                cors_origin_allowed
            response.headers['Access-Control-Allow-Methods'] = \
                'POST, PUT, GET, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = \
                f'{config.get("apitoken_header_name")}, Content-Type'

    return response


def set_cache_control_headers_for_response(response: Response) -> Response:

    # __no_cache__ should not be present when caching is allowed
    allow_cache = '__no_cache__' not in request.environ
    limit_cache_by_cookie = '__limit_cache_by_cookie__' in request.environ

    if 'Pragma' in response.headers:
        del response.headers["Pragma"]

    if allow_cache:
        response.cache_control.public = True
        try:
            cache_expire = config.get('ckan.cache_expires')
            response.cache_control.max_age = cache_expire
            response.cache_control.must_revalidate = True
        except ValueError:
            pass
    else:
        response.cache_control.private = True

    # Invalidate cached pages upon login/logout
    if limit_cache_by_cookie:
        response.vary.add("Cookie")

    return response


def identify_user() -> Response | None:
    '''This function exists only to maintain backward compatibility
    to extensions that still need g.user/g.userobj.

    Note: flask_login now identifies users upon first access to `current_user`.
    '''
    # see if it was proxied first
    g.remote_addr = request.environ.get('HTTP_X_FORWARDED_FOR', '')
    if not g.remote_addr:
        g.remote_addr = request.environ.get('REMOTE_ADDR',
                                            'Unknown IP Address')

    # logout, if a user that was still logged in is deleted.
    if current_user.is_authenticated and not current_user.is_active:
        logout_user()

    # sets the g.user/g.userobj for extensions
    g.user = current_user.name
    g.userobj = current_user if current_user.is_authenticated else None

    # Authentication plugins can break here if a response is returned.
    for item in p.PluginImplementations(p.IAuthenticator):
        if response := item.identify():
            return response

    if current_user.is_authenticated:
        current_user.set_user_last_active()  # type: ignore

    g.author = g.user or g.remote_addr or ""


def set_controller_and_action() -> None:
    g.blueprint, g.view = p.toolkit.get_endpoint()


def set_ckan_current_url(environ: Any) -> None:
    # Current application url
    path_info = environ['PATH_INFO']
    # sort out weird encodings
    path_info = \
        '/'.join(quote(pce, '') for pce in path_info.split('/'))

    qs = environ.get('QUERY_STRING')
    if qs:
        environ['CKAN_CURRENT_URL'] = '%s?%s' % (path_info, qs)
    else:
        environ['CKAN_CURRENT_URL'] = path_info
