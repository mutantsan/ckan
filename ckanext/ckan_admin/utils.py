from __future__ import annotations


import ckan.plugins as p


collect_sections_signal = p.toolkit.signals.ckanext.signal(
    "ckan_admin:collect_config_sections",
    "Collect configuration section from subscribers",
)

collect_config_schemas_signal = p.toolkit.signals.ckanext.signal(
    "ckan_admin:collect_config_schemas",
    "Collect config schemas from subscribers",
)


def ckan_admin_before_request() -> None:
    """Check if user has access to the admin panel.

    Calls `ckan_admin_access` auth function to check if user has access to the
    admin panel view. If you want to change the auth function logic, you can chain it.

    Raises:
        NotAuthorized: If user does not have access to the admin panel

    Example:
        ```python
        from flask import Blueprint, Response

        from ckanext.ckan_admin.utils import ckan_admin_before_request

        blueprint = Blueprint(
            "my_blueprint", __name__, url_prefix="/ckan-admin/my_blueprint"
        )
        blueprint.before_request(ckan_admin_before_request)
        ```
    """
    try:
        p.toolkit.check_access(
            "ckan_admin_access",
            {"user": p.toolkit.current_user.name},
        )
    except p.toolkit.NotAuthorized:
        p.toolkit.abort(
            403, p.toolkit._("Need to be system administrator to administer")
        )
