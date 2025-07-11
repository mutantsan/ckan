from __future__ import annotations

import json
from typing import Any

import ckan.lib.munge as munge
import ckan.plugins as p

import ckanext.ckan_admin.utils as utils
import ckanext.ckan_admin.types as types
from ckanext.ckan_admin.interfaces import ICkanAdmin
from ckanext.ckan_admin.types import SectionConfig, ToolbarButton


_formatter_cache: dict[str, types.Formatter] = {}


def ckan_admin_get_all_formatters() -> dict[str, types.Formatter]:
    """Get all registered tabulator formatters.

    A formatter is a function that takes a column value and can modify its appearance
    in a table.

    Returns:
        A mapping of formatter names to formatter functions
    """
    if _formatter_cache:
        return _formatter_cache

    for plugin in reversed(list(p.PluginImplementations(ICkanAdmin))):
        for name, fn in plugin.get_formatters().items():
            _formatter_cache[name] = fn

    return _formatter_cache


def ckan_admin_get_config_sections() -> list[SectionConfig]:
    """Prepare a config section structure for render.

    Returns:
        A list of sections with their config items
    """
    config_sections = {}

    for _, section in utils.collect_sections_signal.send():
        config_sections.setdefault(
            section["name"], {"name": section["name"], "configs": []}
        )
        config_sections[section["name"]]["configs"].extend(section["configs"])

    sections = list(config_sections.values())
    sections.sort(key=lambda x: x["name"])

    return sections


def ckan_admin_get_toolbar_structure() -> list[ToolbarButton]:
    """Prepare a toolbar structure for render.

    An extension can register its own toolbar buttons by implementing the
    `register_toolbar_button` method in the `ICkanAdmin` interface.

    Returns:
        A list of toolbar button objects
    """
    configuration_subitems = [
        ToolbarButton(
            label=section["name"],
            subitems=[
                ToolbarButton(
                    label=config_item["name"],
                    url=p.toolkit.url_for(config_item["blueprint"]),
                )
                for config_item in section["configs"]
            ],
        )
        for section in ckan_admin_get_config_sections()
    ]

    default_structure = [
        ToolbarButton(
            label=p.toolkit._("Content"),
            icon="fa fa-folder",
            subitems=[
                ToolbarButton(
                    label=p.toolkit._("Datasets"),
                    url=p.toolkit.url_for("ckan_admin_content.datasets"),
                    icon="fa fa-tree",
                ),
                ToolbarButton(
                    label=p.toolkit._("Organisations"),
                    url=p.toolkit.url_for("ckan_admin_content.organisations"),
                    icon="fa fa-building",
                ),
            ],
        ),
        ToolbarButton(
            label=p.toolkit._("Configuration"),
            icon="fa fa-gear",
            url=p.toolkit.url_for("ckan_admin_config_list.index"),
            subitems=configuration_subitems,
        ),
        ToolbarButton(
            label=p.toolkit._("Users"),
            icon="fa fa-user-friends",
            url=p.toolkit.url_for("ckan_admin_user.list"),
            subitems=[
                ToolbarButton(
                    label=p.toolkit._("Add user"),
                    url=p.toolkit.url_for("ckan_admin_user.create"),
                    icon="fa fa-user-plus",
                )
            ],
        ),
        ToolbarButton(
            icon="fa fa-user",
            url=p.toolkit.url_for("user.read", id=p.toolkit.current_user.name),
            label=p.toolkit.current_user.display_name,  # type: ignore
            attributes={
                "title": p.toolkit._("View profile"),
                "class": "ms-lg-auto cad-small",
            },
        ),
        ToolbarButton(
            icon="fa fa-gavel",
            url=p.toolkit.url_for("admin.index"),
            aria_label=p.toolkit._("Old admin"),
            attributes={"title": p.toolkit._("Old admin"), "class": "cad-small"},
        ),
        ToolbarButton(
            icon="fa fa-tachometer",
            url=p.toolkit.url_for("dashboard.datasets"),
            aria_label=p.toolkit._("View dashboard"),
            attributes={"title": p.toolkit._("View dashboard"), "class": "cad-small"},
        ),
        ToolbarButton(
            icon="fa fa-cog",
            url=p.toolkit.url_for("user.edit", id=p.toolkit.current_user.name),
            aria_label=p.toolkit._("Profile settings"),
            attributes={"title": p.toolkit._("Profile settings"), "class": "cad-small"},
        ),
    ]

    default_structure.append(
        ToolbarButton(
            icon="fa fa-sign-out",
            url=p.toolkit.url_for("user.logout"),
            aria_label=p.toolkit._("Log out"),
            attributes={"title": p.toolkit._("Log out")},
        )
    )

    for plugin in reversed(list(p.PluginImplementations(ICkanAdmin))):
        default_structure = plugin.register_toolbar_button(default_structure)

    _toolbar_cache = default_structure

    return default_structure


def ckan_admin_munge_string(value: str) -> str:
    """Munge a string using CKAN's munge_name function.

    Args:
        value: The string to munge

    Returns:
        The munged string
    """
    return munge.munge_name(value)


def ckan_admin_user_add_role_options() -> list[dict[str, str | int]]:
    """Return a list of options for a user add form.

    Returns:
        A list of options for a user add form
    """
    return [
        {"value": "user", "text": "Regular user"},
        {"value": "sysadmin", "text": "Sysadmin"},
    ]


def ckan_admin_build_url_from_params(
    endpoint: str, url_params: dict[str, Any], row: dict[str, Any]
) -> str:
    """Build an action URL based on the endpoint and URL parameters.

    The url_params might contain values like $id, $type, etc.
    We need to replace them with the actual values from the row

    Args:
        endpoint: The endpoint to build the URL for
        url_params: The URL parameters to build the URL for
        row: The row to build the URL for
    """
    params = url_params.copy()

    for key, value in params.items():
        if value.startswith("$"):
            params[key] = row[value[1:]]

    return p.toolkit.url_for(endpoint, **params)


def ckan_admin_dumps(value: Any) -> str:
    """Convert a value to a JSON string.

    Args:
        value: The value to convert to a JSON string

    Returns:
        The JSON string
    """
    return json.dumps(value)
