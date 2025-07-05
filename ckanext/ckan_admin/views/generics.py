from __future__ import annotations

import json
import logging
from abc import abstractmethod
from typing import Any

from flask import Response, jsonify
from flask.views import MethodView

import ckan.plugins as p

import ckanext.ckan_admin.types as types
from ckanext.ckan_admin.table import TableDefinition

log = logging.getLogger(__name__)


class CkanAdminTableView(MethodView):
    def __init__(
        self,
        table: type[TableDefinition],
        breadcrumb_label: str = "Table",
        page_title: str = "Table",
    ):
        """A generic view to render tables

        Args:
            table: a table definition
            render_template (optional): a path to a render template
        """
        self.table = table
        self.breadcrumb_label = breadcrumb_label
        self.page_title = page_title

    def get(self) -> str | Response:
        """Render a table

        If the data argument is provided, returns the table data
        """
        table = self.table()  # type: ignore

        if p.toolkit.request.args.get("data"):
            return jsonify(table.get_data())

        return table.render_table(
            breadcrumb_label=self.breadcrumb_label, page_title=self.page_title
        )

    def post(self) -> Response:
        """Handle global actions on a table"""
        global_action = p.toolkit.request.form.get("global_action")
        rows = p.toolkit.request.form.get("rows")

        action_func = self.get_global_action(global_action) if global_action else None

        if not action_func or not rows:
            return jsonify(
                {
                    "success": False,
                    "errors": [p.toolkit._("The global action is not implemented")],
                }
            )

        errors = []

        for row in json.loads(rows):
            success, error = action_func(row)

            if not success:
                log.debug("Error during global action %s: %s", global_action, error)
                errors.append(error)

        return jsonify({"success": not errors, "errors": errors})

    @abstractmethod
    def get_global_action(self, value: str) -> types.GlobalActionHandler | None:
        pass
