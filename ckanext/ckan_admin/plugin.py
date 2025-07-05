from __future__ import annotations

import ckan.plugins as p
from ckan.types import SignalMapping

import ckanext.ckan_admin.types as types
import ckanext.ckan_admin.formatters as formatters
from ckanext.ckan_admin import utils
from ckanext.ckan_admin.interfaces import ICkanAdmin


@p.toolkit.blanket.blueprints
@p.toolkit.blanket.auth_functions
@p.toolkit.blanket.helpers
class CkanAdminPlugin(p.SingletonPlugin):
    p.implements(p.IConfigurer)
    p.implements(p.ISignal)
    p.implements(p.ITemplateHelpers)
    p.implements(ICkanAdmin, inherit=True)

    # IConfigurer

    def update_config(self, config_: p.toolkit.CKANConfig):
        p.toolkit.add_template_directory(config_, "templates")
        p.toolkit.add_resource("assets", "ckan_admin")

    # ISignal

    def get_signal_subscriptions(self) -> SignalMapping:
        return {
            utils.collect_sections_signal: [
                self.collect_config_sections_subscriber,
            ],
        }

    @classmethod
    def collect_config_sections_subscriber(cls, sender: None):
        return types.SectionConfig(
            name=p.toolkit._("Basic site settings"),
            configs=[
                types.ConfigurationItem(
                    name=p.toolkit._("CKAN configuration"),
                    info=p.toolkit._("CKAN site config options"),
                    blueprint="ckan_admin_basic.config",
                ),
            ],
        )

    # IAdminPanel

    def get_formatters(self) -> dict[str, types.Formatter]:
        return formatters.get_formatters()
