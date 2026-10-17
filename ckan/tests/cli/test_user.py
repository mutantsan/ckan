
import pytest

import ckan.model as model
from ckan.tests.helpers import call_action
from ckan.cli.cli import ckan
from ckan.tests import factories


@pytest.mark.usefixtures("non_clean_db")
class TestUserAdd:

    def test_cli_user_add_valid_args(self, cli):
        """Command shouldn't raise SystemExit when valid args are provided.
        """
        args = [
            "user",
            "add",
            factories.User.stub().name,
            "password=password123",
            "fullname=Berty Guffball",
            "email=" + factories.User.stub().email,
        ]
        result = cli.invoke(ckan, args)

        assert not result.exit_code, result.output

    def test_cli_user_add_no_args(self, cli):
        """Command with no args raises SystemExit.
        """
        result = cli.invoke(ckan, ['user', 'add'])
        assert result.exit_code

    def test_cli_user_add_no_fullname(self, cli):
        """Command shouldn't raise SystemExit when fullname arg not present.
        """
        args = [
            "user",
            "add",
            factories.User.stub().name,
            "password=password123",
            "email=" + factories.User.stub().email,
        ]
        result = cli.invoke(ckan, args)

        assert not result.exit_code, result.output

    def test_cli_user_add_unicode_fullname_unicode_decode_error(self, cli):
        """
        Command shouldn't raise UnicodeDecodeError when fullname contains
        characters outside of the ascii characterset.
        """
        args = [
            "user",
            "add",
            factories.User.stub().name,
            "password=password123",
            "fullname=Harold Müffintøp",
            "email=" + factories.User.stub().email,
        ]
        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output

    def test_cli_user_add_unicode_fullname_system_exit(self, cli):
        """
        Command shouldn't raise SystemExit when fullname contains
        characters outside of the ascii characterset.
        """
        args = [
            "user",
            "add",
            factories.User.stub().name,
            "password=password123",
            "fullname=Harold Müffintøp",
            "email=" + factories.User.stub().email,
        ]
        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output


@pytest.mark.usefixtures("non_clean_db")
class TestApiToken:

    def test_revoke(self, cli):
        user = factories.User()
        call_action("api_token_create", user=user["id"], name="first token")
        tid = model.Session.query(model.ApiToken).first().id

        # tid must be prefixed by --. When it starts with a hyphen it treated
        # as a flag otherwise.
        args = ["user", "token", "revoke", "--", tid]
        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output
        assert "API Token has been revoked" in result.output

        result = cli.invoke(ckan, args)
        assert result.exit_code == 1
        assert "API Token not found" in result.output

    def test_list(self, cli):
        user = factories.User()
        call_action("api_token_create", user=user["id"], name="first token")
        call_action("api_token_create", user=user["id"], name="second token")
        args = [
            "user",
            "token",
            "list",
            user["name"],
        ]
        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output
        tokens = model.Session.query(model.ApiToken.id).filter_by(
            user_id=user["id"])
        assert all(token.id in result.output for token in tokens)

    def test_add_with_extras(self, cli):
        """Command shouldn't raise SystemExit when valid args are provided.
        """
        user = factories.User()
        args = [
            "user",
            "token",
            "add",
            user["name"],
            "new_token",
            """--json={"x": "y"}""",
        ]

        initial = model.Session.query(model.ApiToken).count()
        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output
        assert model.Session.query(model.ApiToken).count() == initial + 1

        args = [
            "user",
            "token",
            "add",
            user["name"],
            "new_token",
            "x=1",
            "y=2"
        ]

        result = cli.invoke(ckan, args)
        assert not result.exit_code, result.output
        assert model.Session.query(model.ApiToken).count() == initial + 2

        args = [
            "user",
            "token",
            "add",
            user["name"],
            "new_token",
            "x",
            "y=2"
        ]

        result = cli.invoke(ckan, args)
        assert result.exit_code == 1
        assert model.Session.query(model.ApiToken).count() == initial + 2
