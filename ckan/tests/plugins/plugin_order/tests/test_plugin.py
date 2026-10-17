
import pytest

class TestPluginOrder:

    @pytest.mark.ckan_config("ckan.plugins", "test_plugin_order_first test_plugin_order_second")
    @pytest.mark.usefixtures("with_plugins")
    def test_templates_and_helpers_order_first_second(self, app):
        res = app.get('/')
        assert "Template of First plugin, helper response: First helper" in res.body


    @pytest.mark.ckan_config("ckan.plugins", "test_plugin_order_second test_plugin_order_first ")
    @pytest.mark.usefixtures("with_plugins")
    def test_templates_and_helpers_order_second_first(self, app):
        res = app.get('/')
        assert "Template of Second plugin, helper response: Second helper" in res.body
