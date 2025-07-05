from __future__ import annotations

from ckan.plugins.interfaces import Interface

import ckanext.ckan_admin.types as types


class ICkanAdmin(Interface):
    """Extends the functionallity of the Admin Panel."""

    def register_toolbar_button(
        self, toolbar_buttons_list: list[types.ToolbarButton]
    ) -> list[types.ToolbarButton]:
        """Register toolbar buttons.

        Extension will receive the list of toolbar button objects. It can
        modify the list and return it back.

        Example:
            ```python
            import ckanext.ckan_admin.types as types

            def register_toolbar_button(toolbar_buttons_list):
                toolbar_buttons_list.append(
                    types.ToolbarButton(
                        label='My Button',
                        url=tk.h.url_for('my_controller.my_action'),
                        icon='fa-star',
                        attributes={'class': 'text'},
                    )
                )
                return toolbar_buttons_list
            ```

        Returns:
            A list of toolbar button objects
        """
        return toolbar_buttons_list

    def get_formatters(self) -> dict[str, types.Formatter]:
        """Allows an extension to register its own tabulator formatters.

        Example:
            ```python
            def get_formatters():
                return {'format_date': format_date}
            ```

        Returns:
            A mapping of formatter names to tabulator formatter functions
        """
        return {}
