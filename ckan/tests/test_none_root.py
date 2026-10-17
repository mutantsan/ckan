
import pytest


@pytest.mark.ckan_config("ckan.root_path", "/data/{{LANG}}")
@pytest.mark.ckan_config("ckan.plugins", "example_theme_v15_webassets")
@pytest.mark.usefixtures("with_plugins")
def test_resource_url(app):
    content = app.get("/").body
    if "example_theme.css" not in content:
        assert "example_theme.min.css" in content
    assert 'href="/data/webassets/example_theme' in content
