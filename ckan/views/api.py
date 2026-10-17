from __future__ import annotations

import os
import logging
import html
import datetime

from typing import Any
from collections.abc import Callable

from flask import Blueprint, make_response

from werkzeug.exceptions import BadRequest
from werkzeug.datastructures import MultiDict

import ckan.model as model
from ckan.common import json, _, g, request, current_user
from ckan.lib.helpers import url_for
from ckan.lib.i18n import get_locales_from_config, get_js_translations_dir
from ckan.lib.lazyjson import LazyJSONObject

from ckan.lib.navl.dictization_functions import DataError
from ckan.logic import get_action, ValidationError, NotFound, NotAuthorized
from ckan.lib.search import (
    SearchError, SearchIndexError, SearchQueryError, SolrConnectionError
)
from ckan.types import Context, Response, ActionResult


log = logging.getLogger(__name__)

CONTENT_TYPES = {
    'text': 'text/plain;charset=utf-8',
    'html': 'text/html;charset=utf-8',
    'json': 'application/json;charset=utf-8',
    'javascript': 'application/javascript;charset=utf-8',
}

API_REST_DEFAULT_VERSION = 1

API_DEFAULT_VERSION = 3
API_MAX_VERSION = 3

api = Blueprint('api', __name__, url_prefix='/api')


def _json_serial(obj: Any):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError("Unhandled Object")


def _finish(status_int: int,
            response_data: Any = None,
            content_type: str = 'text',
            headers: dict[str, Any] | None = None) -> Response:
    '''When a controller method has completed, call this method
    to prepare the response.

    :param status_int: The HTTP status code to return
    :type status_int: int
    :param response_data: The body of the response
    :type response_data: object if content_type is `text` or `json`,
        a string otherwise
    :param content_type: One of `text`, `html` or `json`. Defaults to `text`
    :type content_type: string
    :param headers: Extra headers to serve with the response
    :type headers: dict

    :rtype: response object. Return this value from the view function
        e.g. return _finish(404, 'Dataset not found')
    '''
    assert isinstance(status_int, int)
    response_msg = ''
    if headers is None:
        headers = {}
    if response_data is not None:
        headers['Content-Type'] = CONTENT_TYPES[content_type]
        if content_type == 'json':
            response_msg = json.dumps(
                response_data,
                default=_json_serial,   # handle datetime objects
                for_json=True)  # handle objects with for_json methods
        else:
            response_msg = response_data
        # Support JSONP callback.
        if (status_int == 200 and 'callback' in request.args and
                request.method == 'GET'):
            # escape callback to remove '<', '&', '>' chars
            callback = html.escape(request.args['callback'])
            response_msg = _wrap_jsonp(callback, response_msg)
            headers['Content-Type'] = CONTENT_TYPES['javascript']
    return make_response((response_msg, status_int, headers))


def _finish_ok(response_data: Any = None,
               content_type: str = 'json',
               resource_location: str | None = None) -> Response:
    '''If a controller method has completed successfully then
    calling this method will prepare the response.

    :param response_data: The body of the response
    :type response_data: object if content_type is `text` or `json`,
        a string otherwise
    :param content_type: One of `text`, `html` or `json`. Defaults to `json`
    :type content_type: string
    :param resource_location: Specify this if a new resource has just been
        created and you need to add a `Location` header
    :type headers: string

    :rtype: response object. Return this value from the view function
        e.g. return _finish_ok(pkg_dict)
    '''
    status_int = 200
    headers = None
    if resource_location:
        status_int = 201
        try:
            resource_location = str(resource_location)
        except Exception as inst:
            msg = \
                "Couldn't convert '%s' header value '%s' to string: %s" % \
                ('Location', resource_location, inst)
            raise Exception(msg)
        headers = {'Location': resource_location}

    return _finish(status_int, response_data, content_type, headers)


def _finish_bad_request(extra_msg: str | None = None) -> Response:
    response_data = _('Bad request')
    if extra_msg:
        response_data = _('Bad request: %s') % extra_msg
    else:
        response_data = _('Bad request')
    return _finish(400, response_data, 'json')


def _wrap_jsonp(callback: str, response_msg: str) -> str:
    return f'{callback}({response_msg});'


def _get_request_data(try_url_params: bool = False) -> dict[str, Any]:
    '''Returns a dictionary, extracted from a request.

    If there is no data, None or "" is returned.
    ValueError will be raised if the data is not a JSON-formatted dict.

    The data is retrieved as a JSON-encoded dictionary from the request
    body.  Or, if the `try_url_params` argument is True and the request is
    a GET request, then an attempt is made to read the data from the url
    parameters of the request.

    try_url_params
        If try_url_params is False, then the data_dict is read from the
        request body.

        If try_url_params is True and the request is a GET request then the
        data is read from the url parameters.  The resulting dict will only
        be 1 level deep, with the url-param fields being the keys.  If a
        single key has more than one value specified, then the value will
        be a list of strings, otherwise just a string.

    '''
    def mixed(multi_dict: MultiDict[str, Any]) -> dict[str, Any]:
        '''Return a dict with values being lists if they have more than one
           item or a string otherwise
        '''
        out: dict[str, Any] = {}
        for key, value in multi_dict.to_dict(flat=False).items():
            out[key] = value[0] if len(value) == 1 else value
        return out

    if not try_url_params and request.method == 'GET':
        raise ValueError('Invalid request. Please use POST method '
                         'for your request')

    request_data: dict[str, Any] | Any = {}
    if request.method in ['POST', 'PUT'] and request.form:
        values = list(request.form.values())
        if (len(values) == 1 and
                values[0] in ['1', '']):
            try:
                keys = list(request.form.keys())
                request_data = json.loads(keys[0])
            except ValueError as e:
                raise ValueError(
                    'Error decoding JSON data. '
                    'Error: %r '
                    'JSON data extracted from the request: %r' %
                    (e, request_data))
        else:
            request_data = mixed(request.form)
    elif request.args and try_url_params:
        request_data = mixed(request.args)
    elif (request.data and request.data != b'' and
          request.content_type != 'multipart/form-data'):
        try:
            request_data = request.get_json()
        except BadRequest as e:
            raise ValueError('Error decoding JSON data. '
                             'Error: %r '
                             'JSON data extracted from the request: %r' %
                             (e, request_data))
    if not isinstance(request_data, dict):
        raise ValueError('Request data JSON decoded to %r but '
                         'it needs to be a dictionary.' % request_data)

    if request.method == 'PUT' and not request_data:
        raise ValueError('Invalid request. Please use the POST method for '
                         'your request')
    for field_name, file_ in request.files.items():
        request_data[field_name] = file_
    log.debug('Request data extracted: %r', request_data)

    return request_data


# View functions

def action(logic_function: str, ver: int = API_DEFAULT_VERSION) -> Response:
    '''Main endpoint for the action API (v3)

    Creates a dict with the incoming request data and calls the appropriate
    logic function. Returns a JSON response with the following keys:

        * ``help``: A URL to the docstring for the specified action
        * ``success``: A boolean indicating if the request was successful or
                an exception was raised
        * ``result``: The output of the action, generally an Object or an Array
        * ``changed_entities``: types and ids of entities created, updated
                or deleted as a result of this action (for some actions)
    '''

    # Check if action exists
    try:
        function = get_action(logic_function)
    except KeyError:
        msg = f'Action name not known: {logic_function}'
        log.info(msg)
        return _finish_bad_request(msg)

    context: Context = {
        'user': current_user.name,
        'api_version': ver,
        'auth_user_obj': current_user
    }
    model.Session()._context = context

    return_dict: dict[str, Any] = {
        'help': url_for('api.action',
                         logic_function='help_show',
                         ver=ver,
                         name=logic_function,
                         _external=True,
                         )
    }

    # Get the request data
    try:
        side_effect_free = getattr(function, 'side_effect_free', False)

        request_data = _get_request_data(
            try_url_params=side_effect_free)
    except ValueError as inst:
        log.info('Bad Action API request data: %s', inst)
        return _finish_bad_request(
            _('JSON Error: %s') % inst)

    if 'callback' in request_data:
        del request_data['callback']
        g.user = None
        g.userobj = None
        context['user'] = ''
        context['auth_user_obj'] = None

    # Call the action function, catch any exception
    try:
        result = function(context, request_data)
        return_dict['success'] = True
        return_dict['result'] = result
        if 'changed_entities' in context:
            return_dict['changed_entities'] = {
                typ: sorted(ids)
                for typ, ids in context['changed_entities'].items()
            }
    except DataError as e:
        log.info('Format incorrect (Action API): %s - %s',
                 e.error, request_data)
        return_dict['error'] = {'__type': 'Integrity Error',
                                 'message': e.error,
                                 'data': request_data}
        return_dict['success'] = False
        return _finish(400, return_dict, content_type='json')
    except NotAuthorized as e:
        error_msg = _('Access denied: %s') % e if str(e) else _('Access denied')
        return_dict['error'] = {'__type': 'Authorization Error',
                                 'message': error_msg}
        return_dict['success'] = False
        return _finish(403, return_dict, content_type='json')
    except NotFound as e:
        error_msg = _('Not found: %s') % e if str(e) else _('Not found')
        return_dict['error'] = {'__type': 'Not Found Error',
                                 'message': error_msg}
        return_dict['success'] = False
        return _finish(404, return_dict, content_type='json')
    except ValidationError as e:
        error_dict = e.error_dict
        error_dict['__type'] = 'Validation Error'
        return_dict['error'] = error_dict
        return_dict['success'] = False
        # CS nasty_string ignore
        log.info('Validation error (Action API): %r', str(e.error_dict))
        return _finish(409, return_dict, content_type='json')
    except SearchQueryError as e:
        return_dict['error'] = {'__type': 'Search Query Error',
                                 'message': 'Search Query is invalid: %r' %
                                 e.args}
        return_dict['success'] = False
        return _finish(400, return_dict, content_type='json')
    except SearchError as e:
        return_dict['error'] = {'__type': 'Search Error',
                                 'message': 'Search error: %r' % e.args}
        return_dict['success'] = False
        return _finish(409, return_dict, content_type='json')
    except SearchIndexError as e:
        return_dict['error'] = {
            '__type': 'Search Index Error',
            'message': 'Unable to add package to search index: %s' %
                       str(e)}
        return_dict['success'] = False
        return _finish(500, return_dict, content_type='json')
    except SolrConnectionError:
        return_dict['error'] = {
            '__type': 'Search Connection Error',
            'message': 'Unable to connect to the search server'}
        return_dict['success'] = False
        return _finish(500, return_dict, content_type='json')
    except Exception as e:
        return_dict['error'] = {
            '__type': 'Internal Server Error',
            'message': 'Internal Server Error'}
        return_dict['success'] = False
        log.exception(e)
        return _finish(500, return_dict, content_type='json')

    return _finish_ok(return_dict)


def get_api(ver: int = 1) -> Response:
    '''Root endpoint for the API, returns the version number'''

    response_data = {
        'version': ver
    }
    return _finish_ok(response_data)


def dataset_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('incomplete', '')
    limit = request.args.get('limit', 10)
    package_dicts: ActionResult.PackageAutocomplete = []
    if q:
        context: Context = {
            'user': current_user.name,
            'auth_user_obj': current_user,
        }

        data_dict: dict[str, Any] = {'q': q, 'limit': limit}

        package_dicts = get_action(
            'package_autocomplete')(context, data_dict)

    result_set = {'ResultSet': {'Result': package_dicts}}
    return _finish_ok(result_set)


def tag_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('incomplete', '')
    limit = request.args.get('limit', 10)
    vocab = request.args.get('vocabulary_id', '')
    tag_names: ActionResult.TagAutocomplete = []
    if q:
        context: Context = {
            'user': current_user.name,
            'auth_user_obj': current_user,
        }

        data_dict: dict[str, Any] = {'q': q, 'limit': limit}
        if vocab != '':
            data_dict['vocabulary_id'] = vocab

        tag_names = get_action('tag_autocomplete')(context, data_dict)

    result_set = {
        'ResultSet': {
            'Result': [{'Name': tag} for tag in tag_names]
        }
    }
    return _finish_ok(result_set)


def format_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('incomplete', '')
    limit = request.args.get('limit', 5)
    formats: ActionResult.FormatAutocomplete = []
    if q:
        context: Context = {
            'user': current_user.name,
            'auth_user_obj': current_user,
        }
        data_dict: dict[str, Any] = {'q': q, 'limit': limit}
        formats = get_action('format_autocomplete')(context, data_dict)

    result_set = {
        'ResultSet': {
            'Result': [{'Format': format} for format in formats]
        }
    }
    return _finish_ok(result_set)


def user_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('q', '')
    limit = request.args.get('limit', 20)
    ignore_self = request.args.get('ignore_self', False)
    user_list: ActionResult.UserAutocomplete = []
    if q:
        context: Context = {
            'user': current_user.name,
            'auth_user_obj': current_user,
        }

        data_dict: dict[str, Any] = {
            'q': q, 'limit': limit, 'ignore_self': ignore_self}

        user_list = get_action('user_autocomplete')(context, data_dict)
    return _finish_ok(user_list)


def group_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('q', '')
    limit = request.args.get('limit', 20)
    group_list: ActionResult.GroupAutocomplete = []

    if q:
        context: Context = {'user': current_user.name}

        data_dict: dict[str, Any] = {'q': q, 'limit': limit}
        group_list = get_action('group_autocomplete')(context, data_dict)
    return _finish_ok(group_list)


def organization_autocomplete(ver: int = API_REST_DEFAULT_VERSION) -> Response:
    q = request.args.get('q', '')
    limit = request.args.get('limit', 20)
    organization_list = []

    if q:
        context: Context = {'user': current_user.name}
        data_dict: dict[str, Any] = {'q': q, 'limit': limit}
        organization_list = get_action(
            'organization_autocomplete')(context, data_dict)
    return _finish_ok(organization_list)


def i18n_js_translations(
        lang: str,
        ver: int = API_REST_DEFAULT_VERSION) -> str | Response:

    if lang not in get_locales_from_config():
        return _finish_bad_request(f'Unknown locale: {lang}')

    js_translations_folder = get_js_translations_dir()

    source = os.path.join(js_translations_folder, f"{lang}.js")
    if not os.path.exists(source):
        return "{}"
    translations = open(source, encoding="utf-8").read()
    return _finish_ok(LazyJSONObject(translations))


# Routing

# Root
api.add_url_rule('/', view_func=get_api, strict_slashes=False)
api.add_url_rule(f'/<int(min=1, max={API_MAX_VERSION}):ver>',
                 view_func=get_api, strict_slashes=False)

# Action API (v3)

api.add_url_rule('/action/<logic_function>', methods=['GET', 'POST'],
                 view_func=action)
api.add_url_rule(f'/<int(min=3, max={API_MAX_VERSION}):ver>/action/<logic_function>',
                 methods=['GET', 'POST'],
                 view_func=action)


# Util API

util_rules: list[tuple[str, Callable[..., str | Response]]] = [
    ('/util/dataset/autocomplete', dataset_autocomplete),
    ('/util/user/autocomplete', user_autocomplete),
    ('/util/tag/autocomplete', tag_autocomplete),
    ('/util/group/autocomplete', group_autocomplete),
    ('/util/organization/autocomplete', organization_autocomplete),
    ('/util/resource/format_autocomplete', format_autocomplete),
    ('/i18n/<lang>', i18n_js_translations),
]

version_rule = '/<int(min=1, max=2):ver>'
for rule, view_func in util_rules:
    api.add_url_rule(rule, view_func=view_func)
    api.add_url_rule(version_rule + rule, view_func=view_func)
