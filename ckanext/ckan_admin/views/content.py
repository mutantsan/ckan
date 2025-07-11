from __future__ import annotations

from abc import abstractmethod
import logging
from functools import partial
from typing import Any, Optional, Union

import sqlalchemy as sa
from flask import Blueprint, Response
from flask.views import MethodView
from typing_extensions import TypeAlias
from sqlalchemy.orm import Query

import ckan.plugins as p
from ckan import model

import ckanext.ckan_admin.types as types
import ckanext.ckan_admin.utils as ap_utils
from ckanext.ckan_admin.table import (
    ActionDefinition,
    ColumnDefinition,
    GlobalActionDefinition,
    TableDefinition,
    QueryParams,
)
from ckanext.ckan_admin.views.generics import CkanAdminTableView

ContentList: TypeAlias = "list[dict[str, Any]]"

ckan_admin_content = Blueprint("ckan_admin_content", __name__, url_prefix="/ckan-admin")
ckan_admin_content.before_request(ap_utils.ckan_admin_before_request)

log = logging.getLogger(__name__)


class BaseContentListTable(TableDefinition):
    column_names = []

    def get_raw_data(self, params: QueryParams) -> list[dict[str, Any]]:
        offset = (params.page - 1) * params.size
        union_query = self._build_query(params)

        sort_column = params.sort_by or union_query.c.metadata_modified
        sort_func = sa.asc if params.sort_order == "asc" else sa.desc

        paginated_query = (
            model.Session.query(union_query)
            .order_by(sort_func(sort_column))
            .offset(offset)
            .limit(params.size)
        )

        return [dict(zip(self.column_names, row)) for row in paginated_query.all()]

    def get_total_count(self, params: QueryParams) -> int:
        return (
            model.Session.query(sa.func.count())
            .select_from(self._build_query(params))
            .scalar()
        )

    @abstractmethod
    def _build_query(self, params: QueryParams) -> sa.sql.Alias:
        pass


class PackageListTable(BaseContentListTable):
    column_names = [
        "id",
        "name",
        "title",
        "type",
        "author",
        "state",
        "metadata_created",
        "metadata_modified",
    ]

    def __init__(self):
        super().__init__(
            name="datasets",
            ajax_url=p.toolkit.url_for("ckan_admin_content.datasets", data=True),
            columns=[
                ColumnDefinition(field="id", visible=False, filterable=False),
                ColumnDefinition(field="title"),
                ColumnDefinition(field="type"),
                ColumnDefinition(
                    field="author",
                    formatters=[("user_link", {})],
                    tabulator_formatter="html",
                ),
                ColumnDefinition(field="state", resizable=False),
                ColumnDefinition(
                    field="metadata_created",
                    formatters=[("date", {"date_format": "%Y-%m-%d %H:%M"})],
                    resizable=False,
                ),
                ColumnDefinition(
                    field="metadata_modified",
                    formatters=[("date", {"date_format": "%Y-%m-%d %H:%M"})],
                    resizable=False,
                ),
                ColumnDefinition(
                    field="actions",
                    formatters=[("actions", {})],
                    filterable=False,
                    tabulator_formatter="html",
                    sorter=None,
                    resizable=False,
                ),
            ],
            actions=[
                ActionDefinition(
                    name="edit",
                    icon="fa fa-pencil",
                    endpoint="ckan_admin_content.entity_proxy",
                    url_params={
                        "view": "edit",
                        "entity_type": "$type",
                        "entity_id": "$id",
                    },
                ),
                ActionDefinition(
                    name="view",
                    icon="fa fa-eye",
                    endpoint="ckan_admin_content.entity_proxy",
                    url_params={
                        "view": "read",
                        "entity_type": "$type",
                        "entity_id": "$id",
                    },
                ),
            ],
            global_actions=[
                GlobalActionDefinition(action="restore", label="Restore dataset(s)"),
                GlobalActionDefinition(action="delete", label="Delete dataset(s)"),
                GlobalActionDefinition(action="purge", label="Purge dataset(s)"),
            ],
        )

    def _build_query(self, params: QueryParams) -> sa.sql.Alias:
        package_query = model.Session.query(
            model.Package.id.label("id"),
            model.Package.name.label("name"),
            model.Package.title.label("title"),
            model.Package.type.label("type"),
            model.User.name.label("author"),
            model.Package.state.label("state"),
            model.Package.metadata_created.label("metadata_created"),
            model.Package.metadata_modified.label("metadata_modified"),
        ).join(model.User, model.Package.creator_user_id == model.User.id)

        return self.filter_query(package_query, model.Package, params).subquery()


class OrganisationListTable(BaseContentListTable):
    column_names = [
        "id",
        "title",
        "name",
        "type",
        "description",
        "state",
        "metadata_created",
        "metadata_modified",
    ]

    def __init__(self):
        super().__init__(
            name="organisations",
            ajax_url=p.toolkit.url_for("ckan_admin_content.organisations", data=True),
            columns=[
                ColumnDefinition(field="id", visible=False, filterable=False),
                ColumnDefinition(field="title"),
                ColumnDefinition(field="name"),
                ColumnDefinition(field="description"),
                ColumnDefinition(field="state", resizable=False),
                ColumnDefinition(
                    field="metadata_created",
                    formatters=[("date", {"date_format": "%Y-%m-%d %H:%M"})],
                    resizable=False,
                ),
                ColumnDefinition(
                    field="actions",
                    formatters=[("actions", {})],
                    filterable=False,
                    tabulator_formatter="html",
                    sorter=None,
                    resizable=False,
                ),
            ],
            actions=[
                ActionDefinition(
                    name="edit",
                    icon="fa fa-pencil",
                    endpoint="ckan_admin_content.entity_proxy",
                    url_params={
                        "view": "edit",
                        "entity_type": "$type",
                        "entity_id": "$id",
                    },
                ),
                ActionDefinition(
                    name="view",
                    icon="fa fa-eye",
                    endpoint="ckan_admin_content.entity_proxy",
                    url_params={
                        "view": "read",
                        "entity_type": "$type",
                        "entity_id": "$id",
                    },
                ),
            ],
            global_actions=[
                GlobalActionDefinition(
                    action="restore", label="Restore organization(s)"
                ),
                GlobalActionDefinition(action="delete", label="Delete organization(s)"),
                GlobalActionDefinition(action="purge", label="Purge organization(s)"),
            ],
        )

    def _build_query(self, params: QueryParams) -> sa.sql.Alias:
        group_query = model.Session.query(
            model.Group.id.label("id"),
            model.Group.name.label("name"),
            model.Group.title.label("title"),
            model.Group.type.label("type"),
            model.Group.description.label("description"),
            model.Group.state.label("state"),
            model.Group.created.label("metadata_created"),
            model.Group.created.label("metadata_modified")
        ).filter(model.Group.type == "organization")

        return self.filter_query(group_query, model.Group, params).subquery()


class BaseContentListView(CkanAdminTableView):
    patch_action = ""
    purge_action = ""

    def get_global_action(self, value: str) -> types.GlobalActionHandler | None:
        return {
            "restore": partial(self._change_entities_state, is_active=True),
            "delete": partial(self._change_entities_state, is_active=False),
            "purge": partial(self._purge_entities),
        }.get(value)

    @classmethod
    def _change_entities_state(
        cls, row: types.Row, is_active: Optional[bool] = False
    ) -> types.GlobalActionHandlerResult:
        try:
            p.toolkit.get_action(cls.patch_action)(
                {"ignore_auth": True},
                {
                    "id": row["id"],
                    "state": model.State.ACTIVE if is_active else model.State.DELETED,
                },
            )
        except p.toolkit.ObjectNotFound:
            pass
        except p.toolkit.ValidationError as e:
            return False, str(e.error_summary)

        return True, None

    @classmethod
    def _purge_entities(cls, row: types.Row) -> types.GlobalActionHandlerResult:
        try:
            p.toolkit.get_action(cls.purge_action)(
                {"ignore_auth": True}, {"id": row["id"]}
            )
        except p.toolkit.ObjectNotFound:
            pass
        except p.toolkit.ValidationError as e:
            return False, str(e.error_summary)

        return True, None


class PackageListView(BaseContentListView):
    patch_action = "package_patch"
    purge_action = "dataset_purge"


class OrganisationListView(CkanAdminTableView):
    patch_aciton = "organization_patch"
    purge_action = "organization_purge"


class ContentProxyView(MethodView):
    def get(self, view: str, entity_type: str, entity_id: str) -> Union[str, Response]:
        return p.toolkit.redirect_to(f"{entity_type}.{view}", id=entity_id)


ckan_admin_content.add_url_rule(
    "/content/datasets",
    view_func=PackageListView.as_view(
        "datasets",
        table=PackageListTable,
        breadcrumb_label="Datasets",
        page_title="Datasets",
    ),
)

ckan_admin_content.add_url_rule(
    "/content/organisations",
    view_func=OrganisationListView.as_view(
        "organisations",
        table=OrganisationListTable,
        breadcrumb_label="Organisations",
        page_title="Organisations",
    ),
)

ckan_admin_content.add_url_rule(
    "/content/groups",
    view_func=OrganisationListView.as_view(
        "groups",
        table=OrganisationListTable,
        breadcrumb_label="Groups",
        page_title="Groups",
    ),
)

ckan_admin_content.add_url_rule(
    "/content/<view>/<entity_type>/<entity_id>",
    view_func=ContentProxyView.as_view("entity_proxy"),
)
