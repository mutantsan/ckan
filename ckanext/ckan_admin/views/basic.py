from __future__ import annotations


from flask import Blueprint, Response
from flask.views import MethodView

import ckan.lib.app_globals as app_globals
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as p
from ckan.logic.schema import update_configuration_schema
from ckan.views.home import CACHE_PARAMETERS

import ckanext.ckan_admin.utils as ap_utils

ckan_admin_basic = Blueprint("ckan_admin_basic", __name__, url_prefix="/ckan-admin")
ckan_admin_basic.before_request(ap_utils.ckan_admin_before_request)


class ResetView(MethodView):
    def get(self) -> str | Response:
        if "cancel" in p.toolkit.request.args:
            return p.toolkit.redirect_to("ckan_admin_basic.config")
        return p.toolkit.render("ckan_admin/config/confirm_reset.html")

    def post(self) -> Response:
        for item in self._get_config_items():
            model.delete_system_info(item)

        app_globals.reset()
        return p.toolkit.redirect_to("ckan_admin_basic.config")

    def _get_config_items(self) -> list[str]:
        return [
            "ckan.site_title",
            "ckan.theme",
            "ckan.site_description",
            "ckan.site_logo",
            "ckan.site_about",
            "ckan.site_intro_text",
            "ckan.site_custom_css",
            "ckan.homepage_style",
        ]


class ConfigView(MethodView):
    def get(self) -> str:
        return p.toolkit.render(
            "ckan_admin/config/basic.html",
            extra_vars=dict(
                data={
                    key: p.toolkit.config.get(key)
                    for key in update_configuration_schema()
                },
                errors={},
                **self._get_config_options(),
            ),
        )

    def post(self) -> str | Response:
        try:
            req = p.toolkit.request.form.copy()
            req.update(p.toolkit.request.files.to_dict())
            data_dict = logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(
                        logic.parse_params(req, ignore_keys=CACHE_PARAMETERS)
                    )
                )
            )

            del data_dict["save"]
            p.toolkit.get_action("config_option_update")(
                {"user": p.toolkit.current_user.name}, data_dict
            )

        except p.toolkit.ValidationError as e:
            items = self._get_config_options()
            vars = dict(
                data=p.toolkit.request.form,
                errors=e.error_dict,
                error_summary=e.error_summary,
                form_items=items,
                **items,
            )
            return p.toolkit.render("ckan_admin/config/basic.html", extra_vars=vars)

        p.toolkit.h.flash_success(p.toolkit._("Settings have been saved"))

        return p.toolkit.redirect_to("ckan_admin_basic.config")

    def _get_config_options(self) -> dict[str, list[dict[str, str]]]:
        return {
            "homepages": [
                {
                    "value": "1",
                    "text": (
                        "Introductory area, search, featured"
                        " group and featured organization"
                    ),
                },
                {
                    "value": "2",
                    "text": (
                        "Search, stats, introductory area, "
                        "featured organization and featured group"
                    ),
                },
                {"value": "3", "text": "Search, introductory area and stats"},
            ]
        }


ckan_admin_basic.add_url_rule("/config/basic", view_func=ConfigView.as_view("config"))
ckan_admin_basic.add_url_rule(
    "/config/basic/reset", view_func=ResetView.as_view("reset")
)
