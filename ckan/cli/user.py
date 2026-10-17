from __future__ import annotations

import logging
from typing import Optional

import click

import ckan.logic as logic
import ckan.model as model
from ckan.cli import error_shout
from ckan.common import json
from ckan.types import Context
from ckan.lib.helpers import helper_functions as h

log = logging.getLogger(__name__)


@click.group(name='user', short_help='Manage user commands')
@click.help_option('-h', '--help')
def user():
    pass


@user.command('add', short_help='Add new user')
@click.argument('username')
@click.argument('args', nargs=-1)
@click.pass_context
def add_user(ctx: click.Context, username: str, args: list[str]):
    '''Add new user if we use ckan sysadmin add
    or ckan user add
    '''
    # parse args into data_dict
    data_dict = {'name': username}
    for arg in args:
        try:
            field, value = arg.split('=', 1)
            data_dict[field] = value
        except ValueError:
            raise ValueError(
                'Could not parse arg: %r (expected "<option>=<value>)"' % arg
            )

    # Required
    if 'email' not in data_dict:
        data_dict['email'] = click.prompt('Email address ').strip()

    if 'password' not in data_dict:
        data_dict['password'] = click.prompt('Password ', hide_input=True,
                                             confirmation_prompt=True)

    import ckan.logic as logic

    try:
        site_user = logic.get_action('get_site_user')(
            {'ignore_auth': True},
            {}
        )
        context: Context = {
            'ignore_auth': True,
            'user': site_user['name'],
        }
        flask_app = ctx.meta['flask_app']
        # Current user is tested against sysadmin role during model
        # dictization, thus we need request context
        with flask_app.test_request_context():
            user_dict = logic.get_action('user_create')(context, data_dict)
        click.secho("Successfully created user: %s" % user_dict['name'],
                    fg='green', bold=True)
    except logic.ValidationError as e:
        error_shout(e)
        raise click.Abort()


def get_user_str(user: model.User):
    user_str = 'name=%s' % user.name
    if user.name != user.display_name:
        user_str += ' display=%s' % user.display_name
    return user_str


@user.command('list', short_help='List all users')
def list_users():
    import ckan.model as model
    click.secho('Users:')
    users = model.Session.query(model.User).filter_by(state='active')
    click.secho('count = %i' % users.count())
    for user in users:
        click.secho(get_user_str(user))


@user.command('remove', short_help='Remove user')
@click.argument('username')
@click.pass_context
def remove_user(ctx: click.Context, username: str):
    if not username:
        error_shout('Please specify the username to be removed')
        return

    site_user = logic.get_action('get_site_user')({'ignore_auth': True}, {})
    context: Context = {'user': site_user['name']}
    with ctx.meta['flask_app'].test_request_context():
        logic.get_action('user_delete')(context, {'id': username})
        click.secho('Deleted user: %s' % username, fg='green', bold=True)


@user.command('show', short_help='Show user')
@click.argument('username')
def show_user(username: str):
    import ckan.model as model
    if not username:
        error_shout('Please specify the username for the user')
        return
    user = model.User.get(str(username))
    click.secho('User: %s' % user)


@user.command("setpass")
@click.argument("username")
@click.option("-p", "--password", help="New password")
def set_password(username: str, password: str | None):
    """Set password for the user."""
    user = model.User.get(username)
    if not user:
        error_shout("User not found!")
        raise click.Abort()

    click.secho(f"Editing user: {user.name}", fg="yellow")

    if not password:
        password = click.prompt(
            "Password",
            hide_input=True,
            confirmation_prompt=True,
        )

    user.password = password
    model.repo.commit_and_remove()
    click.secho("Password updated!", fg="green", bold=True)


@user.group()
def token():
    """Manage API Tokens"""
    pass


@token.command("add", context_settings=dict(ignore_unknown_options=True))
@click.argument("username")
@click.argument("token_name")
@click.argument("extras", type=click.UNPROCESSED, nargs=-1)
@click.option(
    "--json",
    "json_str",
    metavar="EXTRAS",
    default="{}",
    help="Valid JSON object with additional fields for api_token_create",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Output just the token itself (useful in automated scripts)",
)
def add_token(
        username: str, token_name: str, extras: list[str], json_str: str,
        quiet: bool):
    """Create a new API Token for the given user.

    Arbitrary fields can be passed in the form `key=value` or using
    the --json option, containing a JSON encoded object. When both provided,
    `key=value` fields will take precedence and will replace the
    corresponding keys from the --json object.

    Example:

      ckan user token add john_doe new_token x=y --json '{"prop": "value"}'

    """
    data_dict = json.loads(json_str)
    for chunk in extras:
        try:
            key, value = chunk.split("=")
        except ValueError:
            error_shout(
                f"Extras must be passed as `key=value`. Got: {chunk}"
            )
            raise click.Abort()
        data_dict[key] = value

    data_dict.update({"user": username, "name": token_name})
    try:
        token = logic.get_action("api_token_create")(
            {"ignore_auth": True}, data_dict
        )
    except logic.NotFound as e:
        error_shout(e)
        raise click.Abort()
    if not quiet:
        click.secho("API Token created:", fg="green")
        click.echo("\t", nl=False)
    click.echo(token["token"])


@token.command("revoke")
@click.argument("id")
def revoke_token(id: str):
    """Remove API Token with the given ID"""
    if not model.ApiToken.revoke(id):
        error_shout("API Token not found")
        raise click.Abort()
    click.secho("API Token has been revoked", fg="green")


@token.command("list")
@click.argument("username")
def list_tokens(username: str):
    """List all API Tokens for the given user"""
    try:
        tokens = logic.get_action("api_token_list")(
            {"ignore_auth": True}, {"user": username}
        )
    except logic.NotFound as e:
        error_shout(e)
        raise click.Abort()
    if not tokens:
        click.secho("No tokens have been created for user yet", fg="red")
        return
    click.echo("Tokens([id] name - lastAccess):")

    for token in tokens:
        last_access = token["last_access"]
        if last_access:
            accessed = h.date_str_to_datetime(
                last_access
            ).isoformat(" ", "seconds")

        else:
            accessed = "Never"
        click.echo(
            "\t[{id}] {name} - {accessed}".format(
                name=token["name"], id=token["id"], accessed=accessed
            )
        )
