from __future__ import annotations

import logging
from typing import Any, Union, List, Tuple

from flask import Blueprint
from flask.views import MethodView
from flask.wrappers import Response

import ckan.lib.app_globals as app_globals
import ckan.lib.base as base
from ckan.lib.helpers import helper_functions as h
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic
import ckan.model as model
import ckan.logic.schema
from ckan.common import _, config, request, current_user
from ckan.views.home import CACHE_PARAMETERS

from ckan.types import Context, Query


log = logging.getLogger(__name__)

admin = Blueprint('admin', __name__, url_prefix='/ckan-admin')


def _get_sysadmins() -> Query[model.User]:
    q = model.Session.query(model.User).filter(
        model.User.sysadmin.is_(True),
        model.User.state == 'active')
    return q


def _get_config_items() -> list[str]:
    return [
        'ckan.site_title', 'ckan.theme', 'ckan.site_description',
        'ckan.site_logo', 'ckan.site_about', 'ckan.site_intro_text',
        'ckan.site_custom_css'
    ]


@admin.before_request
def before_request() -> None:
    try:
        context: Context = {
            "user": current_user.name,
            "auth_user_obj": current_user
        }
        logic.check_access('sysadmin', context)
    except logic.NotAuthorized:
        base.abort(403, _('Need to be system administrator to administer'))


def index() -> str:
    data = dict(sysadmins=[a.name for a in _get_sysadmins()])
    return base.render('admin/index.html', extra_vars=data)


class ResetConfigView(MethodView):
    def get(self) -> str | Response:
        if 'cancel' in request.args:
            return h.redirect_to('admin.config')
        return base.render('admin/confirm_reset.html', extra_vars={})

    def post(self) -> Response:
        # remove sys info items
        for item in _get_config_items():
            model.delete_system_info(item)
        # reset to values in config
        app_globals.reset()
        return h.redirect_to('admin.config')


class ConfigView(MethodView):
    def get(self) -> str:
        schema = ckan.logic.schema.update_configuration_schema()
        data = {}
        for key in schema:
            data[key] = config.get(key)

        vars: dict[str, Any] = dict(data=data, errors={})

        return base.render('admin/config.html', extra_vars=vars)

    def post(self) -> str | Response:
        try:
            req = request.form.copy()
            req.update(request.files.to_dict())
            data_dict = logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(
                        logic.parse_params(req,
                                           ignore_keys=CACHE_PARAMETERS))))

            del data_dict['save']
            data = logic.get_action('config_option_update')({
                'user': current_user.name
            }, data_dict)

        except logic.ValidationError as e:
            data = request.form
            errors = e.error_dict
            error_summary = e.error_summary
            vars = dict(data=data,
                        errors=errors,
                        error_summary=error_summary)
            return base.render('admin/config.html', extra_vars=vars)

        return h.redirect_to('admin.config')


class TrashView(MethodView):

    def __init__(self):
        self.deleted_packages = self._get_deleted_datasets()
        self.deleted_orgs = model.Session.query(model.Group).filter_by(
            state=model.State.DELETED, is_organization=True)
        self.deleted_groups = model.Session.query(model.Group).filter_by(
            state=model.State.DELETED, is_organization=False)

        self.deleted_entities = {
            'package': self.deleted_packages,
            'organization': self.deleted_orgs,
            'group': self.deleted_groups
        }
        self.messages = {
            'confirm': {
                'all': _('Are you sure you want to purge everything?'),
                'package': _('Are you sure you want to purge datasets?'),
                'organization':
                    _('Are you sure you want to purge organizations?'),
                'group': _('Are you sure you want to purge groups?')
            },
            'success': {
                'package': _('{number} datasets have been purged'),
                'organization': _('{number} organizations have been purged'),
                'group': _('{number} groups have been purged')
            },
            'empty': {
                'package': _('There are no datasets to purge'),
                'organization': _('There are no organizations to purge'),
                'group': _('There are no groups to purge')
            }
        }

    def _get_deleted_datasets(
        self
    ) -> Query[model.Package] | list[Any]:
        if config.get('ckan.search.remove_deleted_packages'):
            return self._get_deleted_datasets_from_db()
        else:
            return self._get_deleted_datasets_from_search_index()

    def _get_deleted_datasets_from_db(self) -> Query[model.Package]:
        return model.Session.query(
            model.Package
        ).filter_by(
            state=model.State.DELETED
        )

    def _get_deleted_datasets_from_search_index(self) -> list[Any]:
        package_search = logic.get_action('package_search')
        search_params = {
            'fq': '+state:deleted',
            'include_private': True,
        }
        base_results = package_search(
            {'ignore_auth': True},
            search_params
        )

        return base_results['results']

    def _get_actions_and_entities(
        self,
    ) -> tuple[tuple[str, ...], tuple[list[Any], ...]]:
        actions = ('dataset_purge', 'group_purge', 'organization_purge')
        entities = tuple(self.deleted_entities.values())
        return actions, entities

    def get(self) -> str:
        ent_type = request.args.get('name')

        if ent_type:
            return base.render('admin/snippets/confirm_delete.html',
                               extra_vars={
                                   'ent_type': ent_type,
                                   'messages': self.messages})

        data = dict(data=self.deleted_entities, messages=self.messages)
        return base.render('admin/trash.html', extra_vars=data)

    def post(self) -> Response:
        if 'cancel' in request.form:
            return h.redirect_to('admin.trash')

        req_action = request.form.get('action', '')
        if req_action == 'all':
            self.purge_all()
        elif req_action in ('package', 'organization', 'group'):
            self.purge_entity(req_action)
        else:
            h.flash_error(_('Action not implemented.'))
        return h.redirect_to('admin.trash')

    def purge_all(self):
        actions, entities = self._get_actions_and_entities()
        for action, deleted_entities in zip(actions, entities):
            for entity in deleted_entities:
                ent_id = entity.id if hasattr(entity, 'id') \
                    else entity['id']
                logic.get_action(action)(
                    {'user': current_user.name}, {'id': ent_id}
                )
            model.Session.remove()
        h.flash_success(_('Massive purge complete'))

    def purge_entity(self, ent_type: str):
        entities = self.deleted_entities[ent_type]
        number = len(entities) if isinstance(entities, list) \
            else entities.count()

        for ent in entities:
            entity_id = ent.id if hasattr(ent, 'id') else ent['id']
            logic.get_action(self._get_purge_action(ent_type))(
                {'user': current_user.name},
                {'id': entity_id}
            )

        model.Session.remove()
        h.flash_success(self.messages['success'][ent_type].format(
            number=number
        ))

    @staticmethod
    def _get_purge_action(ent_type: str) -> str:
        actions = {
            "package": "dataset_purge",
            "organization": "organization_purge",
            "group": "group_purge",
        }

        return actions[ent_type]


admin.add_url_rule(
    '/', view_func=index, methods=['GET'], strict_slashes=False
)
admin.add_url_rule('/reset_config',
                   view_func=ResetConfigView.as_view('reset_config'))
admin.add_url_rule('/config', view_func=ConfigView.as_view('config'))
admin.add_url_rule('/trash', view_func=TrashView.as_view('trash'))
