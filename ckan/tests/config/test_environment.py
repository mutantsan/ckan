
import os

import pytest

import ckan.plugins as p
from ckan.config import environment
from ckan.exceptions import CkanConfigurationException

ENV_VAR_LIST = [
    ("CKAN_SQLALCHEMY_URL", "postgresql://mynewsqlurl/"),
    ("CKAN_DATASTORE_WRITE_URL", "http://mynewdbwriteurl/"),
    ("CKAN_DATASTORE_READ_URL", "http://mynewdbreadurl/"),
    ("CKAN_SOLR_URL", "http://mynewsolrurl/solr"),
    ("CKAN_SITE_ID", "my-site"),
    ("CKAN_SMTP_SERVER", "mail.example.com"),
    ("CKAN_SMTP_STARTTLS", "True"),
    ("CKAN_SMTP_USER", "my_user"),
    ("CKAN_SMTP_PASSWORD", "password"),
    ("CKAN_SMTP_MAIL_FROM", "server@example.com"),
    ("CKAN_MAX_UPLOAD_SIZE_MB", "50"),
]


@pytest.fixture
def reset_env():
    """Reset all environment variables that were patched during tests.

    """
    yield
    for env_var, _ in ENV_VAR_LIST:
        if os.environ.get(env_var, None):
            del os.environ[env_var]
    p.plugins_update()


@pytest.mark.usefixtures("reset_env")
def test_update_config_env_vars(ckan_config):
    """
    Setting an env var from the whitelist will set the appropriate option
    in config object.
    """
    for env_var, value in ENV_VAR_LIST:
        os.environ.setdefault(env_var, value)
    p.plugins_update()

    assert ckan_config["solr_url"] == "http://mynewsolrurl/solr"
    assert ckan_config["sqlalchemy.url"] == "postgresql://mynewsqlurl/"
    assert (
        ckan_config["ckan.datastore.write_url"] == "http://mynewdbwriteurl/"
    )
    assert ckan_config["ckan.datastore.read_url"] == "http://mynewdbreadurl/"
    assert ckan_config["ckan.site_id"] == "my-site"
    assert ckan_config["smtp.server"] == "mail.example.com"
    assert ckan_config["smtp.starttls"] is True
    assert ckan_config["smtp.user"] == "my_user"
    assert ckan_config["smtp.password"] == "password"
    assert ckan_config["smtp.mail_from"] == "server@example.com"
    assert ckan_config["ckan.max_resource_size"] == 50


@pytest.mark.ckan_config("ckan.site_url", "")
def test_missing_siteurl():
    with pytest.raises(CkanConfigurationException):
        environment.update_config()


@pytest.mark.ckan_config("ckan.site_url", "demo.ckan.org")
def test_siteurl_missing_schema():
    with pytest.raises(RuntimeError):
        environment.update_config()


@pytest.mark.ckan_config("ckan.site_url", "ftp://demo.ckan.org")
def test_siteurl_wrong_schema():
    with pytest.raises(RuntimeError):
        environment.update_config()


@pytest.mark.ckan_config("ckan.site_url", "http://demo.ckan.org/")
def test_siteurl_removes_backslash(ckan_config):
    environment.update_config()
    assert ckan_config["ckan.site_url"] == "http://demo.ckan.org"


@pytest.mark.ckan_config("ckan.display_timezone", "Krypton/Argo City")
def test_missing_timezone():
    with pytest.raises(CkanConfigurationException):
        environment.update_config()


@pytest.mark.ckan_config("plugin_template_paths", [
    os.path.join(os.path.dirname(__file__), "data")
])
def test_plugin_template_paths_reset(app):
    resp = app.get("/about")
    assert "YOU WILL NOT FIND ME" not in resp


@pytest.mark.usefixtures("reset_env")
def test_config_from_envs_are_normalized(ckan_config):
    """ CONFIG_FROM_ENV_VARS takes precedence over
        config file and extensions
        but those settings are not normalized """

    os.environ['CKAN_SMTP_STARTTLS'] = 'false'
    environment.update_config()

    assert ckan_config["smtp.starttls"] is False


@pytest.mark.ckan_config("SECRET_KEY", "super_secret")
@pytest.mark.ckan_config("WTF_CSRF_SECRET_KEY", None)
def test_all_secrets_default_to_SECRET_KEY(ckan_config):

    environment.update_config()

    for key in [
        "SECRET_KEY",
        "WTF_CSRF_SECRET_KEY",
    ]:
        assert ckan_config[key] == "super_secret"

    # Note: api_token.jwt.*.secret are tested in ckan/tests/lib/test_api_token.py


@pytest.mark.ckan_config("beaker.session.secret", "super_secret")
def test_SECRET_KEY_falls_back_to_beaker_session_secret(ckan_config, monkeypatch):

    monkeypatch.delitem(ckan_config, "SECRET_KEY")

    environment.update_config()

    assert ckan_config["SECRET_KEY"] == "super_secret"
