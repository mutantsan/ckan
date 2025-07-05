from __future__ import annotations

from typing import Union

from flask import Blueprint, Response

import ckan.plugins.toolkit as tk

from ckanext.ckan_admin.utils import ckan_admin_before_request

ckan_admin_config_list = Blueprint(
    "ckan_admin_config_list", __name__, url_prefix="/ckan-admin"
)
ckan_admin_config_list.before_request(ckan_admin_before_request)


@ckan_admin_config_list.route("/config")
def index() -> Union[str, Response]:
    return tk.render("ckan_admin/config/config_list.html", extra_vars={})
