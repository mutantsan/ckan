from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

from urllib.parse import urlencode
import csv
from io import StringIO

import ckan.lib.base as base
from ckan.lib.helpers import helper_functions as h
from ckan.lib.helpers import Page
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic
import ckan.lib.search as search
import ckan.model as model
import ckan.authz as authz
import ckan.lib.plugins as lib_plugins
import ckan.plugins as plugins
from ckan.common import g, config, request, current_user, _
from ckan.views.home import CACHE_PARAMETERS
from ckan.views.dataset import _get_search_details

from flask import Blueprint, make_response
from flask.views import MethodView
from flask.wrappers import Response
from ckan.types import Context, DataDict, Schema


NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params

log = logging.getLogger(__name__)

lookup_group_plugin = lib_plugins.lookup_group_plugin
lookup_group_controller = lib_plugins.lookup_group_controller


def _get_group_template(template_type: str,
                        group_type: str | None = None) -> str:
    group_plugin = lookup_group_plugin(group_type)
    method = getattr(group_plugin, template_type)
    try:
        return method(group_type)
    except TypeError as err:
        if 'takes 1' not in str(err) and 'takes exactly 1' not in str(err):
            raise
        return method()


def _show_group_schema(group_type: str | None = None) -> Schema:
    '''This is an interface to manipulate data from the database
     into a format suitable for the form (optional)'''
    return lookup_group_plugin(group_type).show_group_schema()


def _setup_template_variables(context: Context,
                              data_dict: DataDict,
                              group_type: str | None = None) -> None:
    if 'type' not in data_dict:
        data_dict['type'] = group_type
    return lookup_group_plugin(group_type).\
        setup_template_variables(context, data_dict)


def _force_reindex(grp: dict[str, Any]) -> None:
    ''' When the group name has changed, we need to force a reindex
    of the datasets within the group, otherwise they will stop
    appearing on the read page for the group (as they're connected via
    the group name)'''
    group = model.Group.get(grp['name'])
    assert group
    for dataset in group.packages():
        search.rebuild(dataset.name)


def _guess_group_type(expecting_name: bool = False) -> str:
    """
            Guess the type of group from the URL.
            * The default url '/group/xyz' returns None
            * group_type is unicode
            * this handles the case where there is a prefix on the URL
              (such as /data/organization)
        """
    parts: list[str] = request.path.split('/')
    parts = [x for x in parts if x]

    idx = 0
    if expecting_name:
        idx = -1

    gt = parts[idx]

    return gt


def index(group_type: str, is_organization: bool) -> str:
    extra_vars: dict[str, Any] = {}
    page = h.get_page_number(request.args) or 1
    items_per_page = config.get('ckan.datasets_per_page')

    context: Context = {
        'user': current_user.name,
        'for_view': True,
        'with_private': False,
    }

    try:
        action_name = 'organization_list' if is_organization else 'group_list'
        check_access(action_name, context)
    except NotAuthorized:
        base.abort(403, _('Not authorized to see this page'))

    q = request.args.get('q', '')
    sort_by = request.args.get('sort')

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.q = q
    g.sort_by_selected = sort_by

    extra_vars["q"] = q
    extra_vars["sort_by_selected"] = sort_by

    # pass user info to context as needed to view private datasets of
    # orgs correctly
    if current_user.is_authenticated:
        context['user_id'] = current_user.id
        context['user_is_admin'] = current_user.sysadmin  # type: ignore

    try:
        data_dict_global_results: dict[str, Any] = {
            'all_fields': False,
            'q': q,
            'sort': sort_by,
            'type': group_type or 'group',
            'include_dataset_count': True,
            'include_member_count': True,
        }

        action_name = 'organization_list' if is_organization else 'group_list'
        global_results = get_action(action_name)(
            context, data_dict_global_results)
    except ValidationError as e:
        if e.error_dict and e.error_dict.get('message'):
            msg: Any = e.error_dict['message']
        else:
            msg = str(e)
        h.flash_error(msg)
        extra_vars["page"] = Page([], 0)
        extra_vars["group_type"] = group_type
        return base.render(
            _get_group_template('index_template', group_type), extra_vars)

    data_dict_page_results: dict[str, Any] = {
        'all_fields': True,
        'q': q,
        'sort': sort_by,
        'type': group_type or 'group',
        'limit': items_per_page,
        'offset': items_per_page * (page - 1),
        'include_extras': True,
        'include_dataset_count': True,
        'include_member_count': True,
    }

    action_name = 'organization_list' if is_organization else 'group_list'
    page_results = get_action(action_name)(context, data_dict_page_results)

    extra_vars["page"] = Page(
        collection=global_results,
        page=page,
        url=h.pager_url,
        items_per_page=items_per_page, )

    extra_vars["page"].items = page_results
    extra_vars["group_type"] = group_type

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.page = extra_vars["page"]
    return base.render(
        _get_group_template('index_template', group_type), extra_vars)


def _read(id: str | None, limit: int, group_type: str) -> dict[str, Any]:
    ''' This is common code used by both read and bulk_process'''
    extra_vars: dict[str, Any] = {}
    context: Context = {
        'user': current_user.name,
        'schema': _show_group_schema(group_type=group_type),
        'for_view': True,
        'extras_as_string': True
    }

    q = request.args.get('q', '')

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.q = q

    # Search within group
    if g.group_dict.get('is_organization'):
        fq = ' owner_org:"%s"' % g.group_dict.get('id')
    else:
        fq = ' groups:"%s"' % g.group_dict.get('name')

    extra_vars["q"] = q

    g.description_formatted = \
        h.render_markdown(g.group_dict.get('description'))

    context['return_query'] = True

    page = h.get_page_number(request.args)

    # most search operations should reset the page counter:
    params_nopage = [(k, v) for k, v in request.args.items(multi=True)
                     if k != 'page']
    sort_by = request.args.get('sort', None)

    def search_url(params: Any) -> str:
        action = 'bulk_process' if getattr(
            g, 'action', '') == 'bulk_process' else 'read'
        url = h.url_for('.'.join([group_type, action]), id=id)
        params = [(k, v.encode('utf-8')
                   if isinstance(v, str) else str(v))
                  for k, v in params]
        return url + '?' + urlencode(params)

    def remove_field(
            key: str, value: str | None = None,
            replace: str | None = None):
        controller = lookup_group_controller(group_type)
        return h.remove_url_param(
            key,
            value=value,
            replace=replace,
            controller=controller,
            action='read',
            extras=dict(id=g.group_dict.get('name')))

    extra_vars["remove_field"] = remove_field

    def pager_url(q: Any = None, page: int | None = None):
        params: list[tuple[str, Any]] = list(params_nopage)
        params.append(('page', page))
        return search_url(params)

    details = _get_search_details()
    extra_vars['fields'] = details['fields']
    extra_vars['fields_grouped'] = details['fields_grouped']
    fq += details['fq']
    search_extras = details['search_extras']

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.fields = extra_vars['fields']
    g.fields_grouped = extra_vars['fields_grouped']

    facets: OrderedDict[str, str] = OrderedDict()

    org_label = h.humanize_entity_type(
        'organization',
        h.default_group_type('organization'),
        'facet label') or _('Organizations')

    group_label = h.humanize_entity_type(
        'group',
        h.default_group_type('group'),
        'facet label') or _('Groups')

    default_facet_titles = {
        'organization': org_label,
        'groups': group_label,
        'tags': _('Tags'),
        'res_format': _('Formats'),
        'license_id': _('Licenses')
    }

    for facet in h.facets():
        if facet in default_facet_titles:
            facets[facet] = default_facet_titles[facet]
        else:
            facets[facet] = facet

    # Facet titles
    facets = _update_facet_titles(facets, group_type)

    extra_vars["facet_titles"] = facets

    data_dict: dict[str, Any] = {
        'q': q,
        'fq': fq,
        'include_private': True,
        'facet.field': list(facets.keys()),
        'rows': limit,
        'sort': sort_by,
        'start': (page - 1) * limit,
        'extras': search_extras
    }

    context_ = context.copy()
    context_.pop("schema", None)

    try:
        query = get_action('package_search')(context_, data_dict)
    except search.SearchError as se:
        log.error('Group search error: %r', se.args)
        extra_vars["query_error"] = True
        extra_vars["page"] = Page(collection=[])
    else:
        extra_vars["page"] = Page(
            collection=query['results'],
            page=page,
            url=pager_url,
            item_count=query['count'],
            items_per_page=limit)

        extra_vars["search_facets"] = query['search_facets']
        extra_vars["page"].items = query['results']

        extra_vars["sort_by_selected"] = sort_by

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.facet_titles = facets
    g.page = extra_vars["page"]

    extra_vars["group_type"] = group_type
    _setup_template_variables(context, {'id': id}, group_type=group_type)
    return extra_vars


def _update_facet_titles(
        facets: OrderedDict[str, str],
        group_type: str) -> OrderedDict[str, str]:
    if g.group_dict.get('is_organization'):
        del facets['organization']
    else:
        del facets['groups']
    for plugin in plugins.PluginImplementations(plugins.IFacets):
        facets = (
            plugin.group_facets(facets, group_type, None)
            if group_type == "group"
            else plugin.organization_facets(facets, group_type, None)
        )
    return facets


def _get_group_dict(id: str, is_organization: bool) -> dict[str, Any]:
    ''' returns the result of group_show action or aborts if there is a
    problem '''
    context: Context = {
        'user': current_user.name,
        'for_view': True
    }
    try:
        action_name = "organization_show" if is_organization else "group_show"
        return get_action(action_name)(context, {
            'id': id,
            'include_datasets': False
        })
    except (NotFound, NotAuthorized):

        msg = (
            _("Organization not found")
            if is_organization
            else _("Group not found")
        )
        base.abort(404, msg)


def read(group_type: str,
         is_organization: bool,
         id: str | None = None) -> str | Response:
    extra_vars = {}
    context: Context = {
        'user': current_user.name,
        'schema': _show_group_schema(group_type=group_type),
        'for_view': True
    }
    data_dict: dict[str, Any] = {'id': id, 'type': group_type}

    # unicode format (decoded from utf8)
    q = request.args.get('q', '')

    extra_vars["q"] = q

    limit = config.get('ckan.datasets_per_page')

    try:
        # Do not query for the group datasets when dictizing, as they will
        # be ignored and get requested on the controller anyway
        data_dict['include_datasets'] = False

        # Do not query group members as they aren't used in the view
        data_dict['include_users'] = False

        action_name = "organization_show" if is_organization else "group_show"
        group_dict = get_action(action_name)(context, data_dict)

    except (NotFound, NotAuthorized):
        base.abort(404, _('Group not found'))

    # if the user specified a group id, redirect to the group name
    if data_dict['id'] == group_dict['id'] and \
            data_dict['id'] != group_dict['name']:

        url_with_name = h.url_for(f'{group_type}.read',
                                  id=group_dict['name'])

        return h.redirect_to(
            h.add_url_param(alternative_url=url_with_name))

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.q = q
    g.group_dict = group_dict

    extra_vars = _read(id, limit, group_type)
    try:
        am_following = logic.get_action('am_following_group')(
            {'user': current_user.name}, {'id': id}
        )
    except NotAuthorized:
        # AnonymousUser
        am_following = False

    extra_vars["group_type"] = group_type
    extra_vars["group_dict"] = group_dict
    extra_vars["am_following"] = am_following
    extra_vars["dataset_type"] = h.default_package_type()

    if request.htmx:
        return base.render(
            _get_group_template('read_template_htmx', g.group_dict['type']),
            extra_vars)

    return base.render(
        _get_group_template('read_template', g.group_dict['type']),
        extra_vars)


def about(id: str, group_type: str, is_organization: bool) -> str:
    context: Context = {'user': current_user.name}

    try:
        group_dict = _get_group_dict(id, is_organization)
        group_type = group_dict['type']
    except NotFound:
        base.abort(404, _('Group not found'))
    except NotAuthorized:
        base.abort(403,
                   _('User %r not authorized to edit members of %s') %
                   (current_user.name, id))

    _setup_template_variables(context, {'id': id}, group_type=group_type)

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.group_dict = group_dict
    g.group_type = group_type

    extra_vars: dict[str, Any] = {"group_dict": group_dict,
                                  "group_type": group_type}

    return base.render(
        _get_group_template('about_template', group_type), extra_vars)


def members(id: str, group_type: str, is_organization: bool) -> str:
    context: Context = {'user': current_user.name}

    try:
        data_dict: dict[str, Any] = {'id': id}
        check_access('group_show', context, data_dict)
        members = get_action('member_list')(context, {
            'id': id,
            'object_type': 'user'
        })
        data_dict['include_datasets'] = False
        action_name = "organization_show" if is_organization else "group_show"
        group_dict = get_action(action_name)(context, data_dict)
    except NotFound:
        base.abort(404, _('Group not found'))
    except NotAuthorized:
        base.abort(403,
                   _('User %r not authorized to edit members of %s') %
                   (current_user.name, id))

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.members = members
    g.group_dict = group_dict

    extra_vars: dict[str, Any] = {
        "members": members,
        "group_dict": group_dict,
        "group_type": group_type,
    }

    template_name = (
        "organization/members.html"
        if is_organization else
        "group/members.html"
    )
    return base.render(template_name, extra_vars)


def manage_members(id: str, group_type: str, is_organization: bool) -> str:
    context: Context = {'user': current_user.name}

    try:
        data_dict: dict[str, Any] = {'id': id}
        check_access('group_edit_permissions', context, data_dict)
        members = get_action('member_list')(context, {
            'id': id,
            'object_type': 'user'
        })
        data_dict['include_datasets'] = False
        action_name = "organization_show" if is_organization else "group_show"
        group_dict = get_action(action_name)(context, data_dict)
    except NotFound:
        base.abort(404, _('Group not found'))
    except NotAuthorized:
        base.abort(403,
                   _('User %r not authorized to edit members of %s') %
                   (current_user.name, id))

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.members = members
    g.group_dict = group_dict

    extra_vars: dict[str, Any] = {
        "members": members,
        "group_dict": group_dict,
        "group_type": group_type,
    }
    template_name = (
        "organization/manage_members.html"
        if is_organization
        else "group/manage_members.html"
    )
    return base.render(template_name, extra_vars)


def member_dump(id: str, group_type: str, is_organization: bool):
    group_obj = model.Group.get(id)
    if not group_obj:
        base.abort(404,
                   _('Organization not found')
                   if is_organization
                   else _('Group not found'))

    context: Context = {'user': current_user.name}

    try:
        action_name = (
            "organization_member_create"
            if is_organization else
            "group_member_create"
        )
        check_access(action_name, context, {'id': id})
    except NotAuthorized:
        base.abort(404,
                   _(f'Not authorized to access {group_obj.title} members download'
                     ))

    try:
        members = get_action('member_list')(context, {
            'id': id,
            'object_type': 'user',
            'records_format': 'csv',
            'include_total': False,
        })
    except NotFound:
        base.abort(404, _('Members not found'))

    results = [[_('Username'), _('Email'), _('Name'), _('Role')]]
    for uid, _user, role in members:
        user_obj = model.User.get(uid)
        if not user_obj:
            continue
        results.append([
            user_obj.name,
            user_obj.email,  # type: ignore
            user_obj.fullname if user_obj.fullname else _('N/A'),
            role,
        ])

    output_stream = StringIO()
    output_stream.write('\N{BOM}')  # for Excel handling of non-ASCII
    csv.writer(output_stream).writerows(results)

    file_name = '{org_id}-{members}'.format(
            org_id=group_obj.name,
            members=_('members'))

    output_stream.seek(0)
    response = make_response(output_stream.read())
    output_stream.close()
    content_disposition = f'attachment; filename="{file_name}.csv"'
    content_type = b'text/csv; charset=utf-8'
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = content_disposition

    return response


def member_delete(id: str, group_type: str,
                  is_organization: bool) -> Response | str:
    extra_vars = {}
    if 'cancel' in request.form:
        return h.redirect_to(f'{group_type}.members', id=id)

    context: Context = {'user': current_user.name}

    try:
        action_name = (
            "organization_member_delete"
            if is_organization else
            "group_member_delete"
        )
        check_access(action_name, context, {'id': id})
    except NotAuthorized:
        base.abort(403, _('Unauthorized to delete group %s members') % '')

    try:
        user_id = request.args.get('user')
        if not user_id:
            base.abort(404, _('User not found'))
        if request.method == 'POST':
            action_name = (
                "organization_member_delete"
                if is_organization
                else "group_member_delete"
            )
            get_action(action_name)(context, {
                'id': id,
                'user_id': user_id
            })
            # What if the user removes itself from the group?
            if user_id in [current_user.name, current_user.id]:

                h.flash_notice(_('You are no longer a member of this group.'))
                return h.redirect_to(f'{group_type}.read', id=id)
            h.flash_notice(_('Group member has been deleted.'))
            return h.redirect_to(
                f'{group_type}.manage_members', id=id)
        user_dict = get_action('user_show')(context, {'id': user_id})

    except NotAuthorized:
        base.abort(403, _('Unauthorized to delete group %s members') % '')
    except NotFound:
        base.abort(404, _('Group not found'))
    extra_vars: dict[str, Any] = {
        "user_id": user_id,
        "user_dict": user_dict,
        "group_id": id,
        "group_type": group_type
    }
    template_name = (
        'organization/confirm_delete_member.html'
        if is_organization
        else 'group/confirm_delete_member.html'
    )
    return base.render(template_name, extra_vars)


def follow(id: str, group_type: str,
           is_organization: bool) -> Response | str:
    '''Start following this group.'''
    data_dict = {
        'id': id,
        'include_datasets': True,
        'include_users': False,
    }
    extra_vars = {
        'current_user': current_user,
        'show_nums': True,
    }

    try:
        if is_organization:
            org_dict = get_action('organization_show')({}, data_dict)
            extra_vars['organization'] = org_dict
        else:
            group_dict = get_action('group_show')({}, data_dict)
            extra_vars['group'] = group_dict
    except (NotFound, NotAuthorized):
        msg = _(f'{group_type} not found or you have no permission to view it')
        base.abort(404, msg)

    am_following = False
    error_message = ""
    try:
        get_action('follow_group')({}, data_dict)
        am_following = True
    except ValidationError as e:
        error_message = str(e.error_dict.get('message'))

    extra_vars['error_message'] = error_message
    extra_vars['am_following'] = am_following

    if is_organization:
        return base.render('organization/snippets/info.html', extra_vars)
    return base.render('group/snippets/info.html', extra_vars)


def unfollow(id: str, group_type: str, is_organization: bool) -> str:
    '''Stop following this group.'''
    data_dict = {
        'id': id,
        'include_datasets': True,
        'include_users': False,
        'include_followers': True
    }
    extra_vars = {
        'current_user': current_user,
        'show_nums': True,
    }
    try:
        if is_organization:
            org_dict = get_action('organization_show')({}, data_dict)
            extra_vars['organization'] = org_dict
        else:
            group_dict = get_action('group_show')({}, data_dict)
            extra_vars['group'] = group_dict
    except (NotFound, NotAuthorized):
        msg = _(f'{group_type} not found or you have no permission to view it')
        base.abort(404, msg)

    am_following = True
    error_message = ""
    try:
        get_action('unfollow_group')({}, data_dict)
        am_following = False
    except (ValidationError) as e:
        error_message = e.error_summary

    extra_vars['error_message'] = error_message
    extra_vars['am_following'] = am_following

    if is_organization:
        return base.render('organization/snippets/info.html', extra_vars)
    return base.render('group/snippets/info.html', extra_vars)


def followers(id: str, group_type: str, is_organization: bool) -> str:
    context: Context = {'user': current_user.name}
    group_dict = _get_group_dict(id, is_organization)
    try:
        followers = \
            get_action('group_follower_list')(context, {'id': id})
    except NotAuthorized:
        base.abort(403, _('Unauthorized to view followers %s') % '')

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.group_dict = group_dict
    g.followers = followers

    extra_vars: dict[str, Any] = {
        "group_dict": group_dict,
        "group_type": group_type,
        "followers": followers
    }
    return base.render('group/followers.html', extra_vars)


def admins(id: str, group_type: str, is_organization: bool) -> str:
    group_dict = _get_group_dict(id, is_organization)
    admins = authz.get_group_or_org_admin_ids(id)

    # TODO: Remove
    # ckan 2.9: Adding variables that were removed from c object for
    # compatibility with templates in existing extensions
    g.group_dict = group_dict
    g.admins = admins

    extra_vars: dict[str, Any] = {
        "group_dict": group_dict,
        'group_type': group_type,
        "admins": admins
    }

    return base.render(
        _get_group_template('admins_template', group_dict['type']),
        extra_vars)


class BulkProcessView(MethodView):
    ''' Bulk process view'''

    def _prepare(self, group_type: str, id: str) -> Context:

        # check we are org admin

        context: Context = {
            'user': current_user.name,
            'schema': _show_group_schema(group_type=group_type),
            'for_view': True,
            'extras_as_string': True
        }

        try:
            check_access('bulk_update_public', context, {'org_id': id})
        except NotAuthorized:
            base.abort(403, _('Unauthorized to access'))

        return context

    def get(self, id: str, group_type: str, is_organization: bool) -> str:
        extra_vars = {}
        context = self._prepare(group_type, id)
        data_dict: dict[str, Any] = {'id': id, 'type': group_type}
        data_dict['include_datasets'] = False
        try:
            action_name = (
                "organization_show" if is_organization else "group_show"
            )
            group_dict = get_action(action_name)(context, data_dict)
            group = context['group']
        except NotFound:
            base.abort(404, _('Group not found'))

        if not group_dict['is_organization']:
            # FIXME: better error
            raise Exception('Must be an organization')

        # If no action then just show the datasets
        limit = 500
        # TODO: Remove
        # ckan 2.9: Adding variables that were removed from c object for
        # compatibility with templates in existing extensions
        g.group_dict = group_dict
        extra_vars = _read(id, limit, group_type)
        extra_vars['packages'] = g.page.items
        extra_vars['group_dict'] = group_dict
        extra_vars['group'] = group

        return base.render(
            _get_group_template('bulk_process_template', group_type),
            extra_vars)

    def post(
            self, id: str, group_type: str,
            is_organization: bool) -> Response:
        context = self._prepare(group_type, id)
        data_dict: dict[str, Any] = {'id': id, 'type': group_type}
        user = current_user.name
        try:
            # Do not query for the group datasets when dictizing, as they will
            # be ignored and get requested on the controller anyway
            data_dict['include_datasets'] = False
            action_name = (
                "organization_show" if is_organization else "group_show"
            )
            group_dict = get_action(action_name)(context, data_dict)
        except NotFound:
            group_label = h.humanize_entity_type(
                'organization' if is_organization else 'group',
                group_type,
                'default label') or _(
                    'Organization' if is_organization else 'Group')
            base.abort(404, _(f'{group_label} not found'))
        except NotAuthorized:
            base.abort(403,
                       _('User %r not authorized to edit %s') % (user, id))

        if not group_dict['is_organization']:
            # FIXME: better error
            raise Exception('Must be an organization')

        # TODO: Remove
        # ckan 2.9: Adding variables that were removed from c object for
        # compatibility with templates in existing extensions
        g.group_dict = group_dict

        # use different form names so that ie7 can be detected
        form_names = set([
            "bulk_action.public",
            "bulk_action.delete",
            "bulk_action.private"
        ])
        actions_in_form: set[str] = set(request.form.keys())
        actions = form_names.intersection(actions_in_form)
        # ie7 puts all buttons in form params but puts submitted one twice

        form_dict: dict[str, str] = request.form.to_dict()
        for key, value in form_dict.items():
            if value in ['private', 'public']:
                action = key.split('.')[-1]
                break
        else:
            # normal good browser form submission
            action = actions.pop().split('.')[-1]

        # process the action first find the datasets to perform the action on.
        # they are prefixed by dataset_ in the form data
        datasets = []
        for param in request.form:
            if param.startswith('dataset_'):
                datasets.append(param[8:])

        action_functions = {
            'private': 'bulk_update_private',
            'public': 'bulk_update_public',
            'delete': 'bulk_update_delete',
        }

        data_dict = {'datasets': datasets, 'org_id': group_dict['id']}

        try:
            get_action(action_functions[action])(context, data_dict)
        except NotAuthorized:
            base.abort(403, _('Not authorized to perform bulk update'))
        return h.redirect_to(f'{group_type}.bulk_process', id=id)


class CreateGroupView(MethodView):
    '''Create group view '''

    def _prepare(
            self,
            is_organization: bool,
            data: dict[str, Any] | None = None) -> Context:
        if data and 'type' in data:
            group_type = data['type']
        else:
            group_type = _guess_group_type()
        if data:
            data['type'] = group_type

        context: Context = {
            'user': current_user.name,
            'save': 'save' in request.args,
            'parent': request.args.get('parent', None),
            'group_type': group_type
        }

        try:
            action_name = (
                'organization_create' if is_organization else 'group_create'
            )
            check_access(action_name, context)
        except NotAuthorized:
            base.abort(403, _('Unauthorized to create a group'))

        return context

    def post(self, group_type: str,
             is_organization: bool) -> Response | str:

        context = self._prepare(is_organization)
        try:
            data_dict = clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.form))))
            data_dict.update(clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.files)))
            ))
        except dict_fns.DataError:
            base.abort(400, _('Integrity Error'))
        user = current_user.name
        data_dict['type'] = group_type or 'group'
        data_dict['users'] = [{'name': user, 'capacity': 'admin'}]
        try:
            action_name = (
                'organization_create' if is_organization else 'group_create'
            )
            group = get_action(action_name)(context, data_dict)
        except (NotFound, NotAuthorized):
            base.abort(404, _('Group not found'))
        except ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(group_type, is_organization,
                            data_dict, errors, error_summary)

        return h.redirect_to(
            group['type'] + '.read', id=group['name'])

    def get(self,
            group_type: str,
            is_organization: bool,
            data: dict[str, Any] | None = None,
            errors: dict[str, Any] | None = None,
            error_summary: dict[str, Any] | None = None) -> str:
        context = self._prepare(is_organization)
        data = data or clean_dict(
            dict_fns.unflatten(
                tuplize_dict(
                    parse_params(request.args, ignore_keys=CACHE_PARAMETERS)
                )
            )
        )

        if not data.get('image_url', '').startswith('http'):
            data.pop('image_url', None)
        errors = errors or {}
        error_summary = error_summary or {}
        extra_vars: dict[str, Any] = {
            'data': data,
            'errors': errors,
            'error_summary': error_summary,
            'action': 'new',
            'group_type': group_type
        }
        _setup_template_variables(
            context, data, group_type=group_type)
        form = base.render(
            _get_group_template('group_form', group_type), extra_vars)

        # TODO: Remove
        # ckan 2.9: Adding variables that were removed from c object for
        # compatibility with templates in existing extensions
        g.form = form

        extra_vars["form"] = form
        return base.render(
            _get_group_template('new_template', group_type), extra_vars)


class EditGroupView(MethodView):
    ''' Edit group view'''

    def _prepare(self, is_organization: bool, id: str | None) -> Context:
        data_dict: dict[str, Any] = {'id': id, 'include_datasets': False}

        context: Context = {
            'user': current_user.name,
            'save': 'save' in request.args,
            'for_edit': True,
            'parent': request.args.get('parent', None),
            'id': id
        }

        try:
            action_name = (
                'organization_show' if is_organization else 'group_show'
            )
            get_action(action_name)(context, data_dict)

            action_name = (
                'organization_update' if is_organization else 'group_update'
            )
            check_access(action_name, context, data_dict)
        except NotAuthorized:
            base.abort(403, _('Unauthorized to create a group'))
        except NotFound:
            base.abort(404, _('Group not found'))

        return context

    def post(self,
             group_type: str,
             is_organization: bool,
             id: str | None = None) -> Response | str:
        context = self._prepare(is_organization, id=id)
        try:
            data_dict = clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.form))))
            data_dict.update(clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.files)))
            ))
        except dict_fns.DataError:
            base.abort(400, _('Integrity Error'))
        data_dict['id'] = context['id']
        try:
            action_name = (
                'organization_update' if is_organization else 'group_update'
            )
            group = get_action(action_name)(context, data_dict)
            if id != group['name']:
                _force_reindex(group)
        except (NotFound, NotAuthorized):
            base.abort(404, _('Group not found'))
        except ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            assert id
            return self.get(id, group_type, is_organization,
                            data_dict, errors, error_summary)
        return h.redirect_to(
            group['type'] + '.read', id=group['name'])

    def get(self,
            id: str,
            group_type: str,
            is_organization: bool,
            data: dict[str, Any] | None = None,
            errors: dict[str, Any] | None = None,
            error_summary: dict[str, Any] | None = None) -> str:
        context = self._prepare(is_organization, id=id)
        data_dict: dict[str, Any] = {'id': id, 'include_datasets': False}
        try:
            action_name = (
                'organization_show' if is_organization else 'group_show'
            )
            group_dict = get_action(action_name)(context, data_dict)
        except (NotFound, NotAuthorized):
            base.abort(404, _('Group not found'))
        data = data or group_dict
        assert data is not None
        errors = errors or {}
        extra_vars: dict[str, Any] = {
            'data': data,
            "group_dict": group_dict,
            'errors': errors,
            'error_summary': error_summary,
            'action': 'edit',
            'group_type': group_type
        }

        _setup_template_variables(context, data, group_type=group_type)
        form = base.render(
            _get_group_template('group_form', group_type), extra_vars)

        # TODO: Remove
        # ckan 2.9: Adding variables that were removed from c object for
        # compatibility with templates in existing extensions
        g.grouptitle = group_dict.get('title')
        g.groupname = group_dict.get('name')
        g.data = data
        g.group_dict = group_dict

        extra_vars["form"] = form
        return base.render(
            _get_group_template('edit_template', group_type), extra_vars)


class DeleteGroupView(MethodView):
    '''Delete group view '''

    def _prepare(
            self,
            is_organization: bool,
            id: str | None = None) -> Context:
        context: Context = {'user': current_user.name}
        try:
            action_name = (
                'organization_delete' if is_organization else 'group_delete'
            )
            check_access(action_name, context, {'id': id})
        except NotAuthorized:
            base.abort(403, _('Unauthorized to delete group %s') % '')
        return context

    def post(self,
             group_type: str,
             is_organization: bool,
             id: str | None = None) -> Response:
        context = self._prepare(is_organization, id=id)
        try:
            action_name = (
                'organization_delete' if is_organization else 'group_delete'
            )
            get_action(action_name)(context, {'id': id})
            group_label = h.humanize_entity_type(
                'group',
                group_type,
                'has been deleted') or _('Group')
            h.flash_notice(
                _('%s has been deleted.') % _(group_label))
        except NotAuthorized:
            base.abort(403, _('Unauthorized to delete group %s') % '')
        except NotFound:
            base.abort(404, _('Group not found'))
        except ValidationError as e:
            base.abort(403, _(e.error_dict['message']))

        return h.redirect_to(f'{group_type}.index')

    def get(self,
            group_type: str,
            is_organization: bool,
            id: str | None = None) -> str | Response:
        context = self._prepare(is_organization, id=id)
        action_name = (
            'organization_show' if is_organization else 'group_show'
        )
        group_dict = get_action(action_name)(context, {'id': id})

        if 'cancel' in request.args:
            return h.redirect_to(f'{group_type}.edit', id=id)

        # TODO: Remove
        g.group_dict = group_dict
        extra_vars: dict[str, Any] = {
            "group_dict": group_dict,
            "group_type": group_type
        }
        template_name = (
            "organization/confirm_delete.html"
            if is_organization
            else "group/confirm_delete.html"
        )
        return base.render(template_name, extra_vars)


class MembersGroupView(MethodView):
    '''New members group view'''

    def _prepare(
            self,
            is_organization: bool,
            id: str | None = None) -> Context:
        context: Context = {'user': current_user.name}
        try:
            action_name = (
                'organization_member_create'
                if is_organization
                else 'group_member_create'
            )
            check_access(action_name, context, {'id': id})
        except NotAuthorized:
            base.abort(403,
                       _('Unauthorized to create group %s members') % '')

        return context

    def post(self,
             group_type: str,
             is_organization: bool,
             id: str | None = None) -> Response:
        context = self._prepare(is_organization, id=id)
        data_dict = clean_dict(
            dict_fns.unflatten(tuplize_dict(parse_params(request.form))))
        data_dict['id'] = id

        email = data_dict.get('email')

        if email:
            user_data_dict: dict[str, Any] = {
                'email': email,
                'group_id': data_dict['id'],
                'role': data_dict['role']
            }
            del data_dict['email']

            try:
                user_dict = get_action('user_invite')(context, user_data_dict)
            except ValidationError as e:
                for error in e.error_summary.values():
                    h.flash_error(error)
                return h.redirect_to(
                    f'{group_type}.member_new', id=id)

            data_dict['username'] = user_dict['name']

        try:
            action_name = (
                'organization_member_create'
                if is_organization else
                'group_member_create'
            )
            group_dict = get_action(action_name)(context, data_dict)
        except NotAuthorized:
            base.abort(403, _('Unauthorized to add member to group %s') % '')
        except NotFound:
            base.abort(404, _('Group not found'))
        except ValidationError as e:
            for error in e.error_summary.values():
                h.flash_error(error)
            return h.redirect_to(f'{group_type}.member_new', id=id)

        # TODO: Remove
        g.group_dict = group_dict

        return h.redirect_to(f'{group_type}.manage_members', id=id)

    def get(self,
            group_type: str,
            is_organization: bool,
            id: str | None = None) -> str:
        extra_vars: dict[str, Any] = {}
        context = self._prepare(is_organization, id=id)
        user = request.args.get('user')
        data_dict: dict[str, Any] = {'id': id}
        data_dict['include_datasets'] = False
        action_name = "organization_show" if is_organization else "group_show"
        group_dict = get_action(action_name)(context, data_dict)
        roles = get_action('member_roles_list')(context, {
            'group_type': group_type
        })
        user_dict = {}
        if user:
            user_dict = get_action('user_show')(context, {'id': user})
            user_role =\
                authz.users_role_for_group_or_org(id, user) or 'member'
            # TODO: Remove
            g.user_dict = user_dict
            extra_vars["user_dict"] = user_dict
        else:
            user_role = 'member'

        # TODO: Remove
        g.group_dict = group_dict
        g.roles = roles
        g.user_role = user_role

        extra_vars.update({
            "group_dict": group_dict,
            "roles": roles,
            "user_role": user_role,
            "group_type": group_type,
            "user_dict": user_dict
        })
        template_name = (
            "organization/member_new.html"
            if is_organization
            else "group/member_new.html"
        )
        return base.render(template_name, extra_vars)


group = Blueprint('group', __name__, url_prefix='/group',
                  url_defaults={'group_type': 'group',
                                'is_organization': False})
organization = Blueprint('organization', __name__,
                         url_prefix='/organization',
                         url_defaults={'group_type': 'organization',
                                       'is_organization': True})


def register_group_plugin_rules(blueprint: Blueprint) -> None:
    blueprint.add_url_rule('/', view_func=index, strict_slashes=False)
    blueprint.add_url_rule(
        '/new',
        methods=['GET', 'POST'],
        view_func=CreateGroupView.as_view('new'))
    blueprint.add_url_rule('/<id>', methods=['GET'], view_func=read)
    blueprint.add_url_rule(
        '/edit/<id>', view_func=EditGroupView.as_view('edit'))
    blueprint.add_url_rule('/about/<id>', methods=['GET'], view_func=about)
    blueprint.add_url_rule(
        '/manage_members/<id>',
        methods=['GET', 'POST'],
        view_func=manage_members)
    blueprint.add_url_rule(
        '/member_dump/<id>',
        view_func=member_dump)
    blueprint.add_url_rule(
        '/members/<id>', methods=['GET'], view_func=members)
    blueprint.add_url_rule(
        '/member_new/<id>',
        view_func=MembersGroupView.as_view('member_new'))
    blueprint.add_url_rule(
        '/bulk_process/<id>',
        view_func=BulkProcessView.as_view('bulk_process'))
    blueprint.add_url_rule(
        '/delete/<id>',
        methods=['GET', 'POST'],
        view_func=DeleteGroupView.as_view('delete'))
    blueprint.add_url_rule(
        '/follow/<id>',
        methods=['POST'],
        view_func=follow)
    blueprint.add_url_rule(
        '/unfollow/<id>',
        methods=['POST'],
        view_func=unfollow)
    actions = ['member_delete', 'followers', 'admins']
    for action in actions:
        blueprint.add_url_rule(
            f'/{action}/<id>',
            methods=['GET', 'POST'],
            view_func=globals()[action])


register_group_plugin_rules(group)
register_group_plugin_rules(organization)
