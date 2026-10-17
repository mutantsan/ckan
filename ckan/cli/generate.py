from __future__ import annotations

import contextlib
import os
import json
from packaging.version import Version
import shutil

import alembic.command
import click
from alembic.config import Config as AlembicConfig
from werkzeug.utils import import_string

import ckan
from ckan import logic
from ckan.cli.db import _resolve_alembic_config

import string
from ckan.cli import error_shout
from ckan.common import config_declaration, config


class CKANAlembicConfig(AlembicConfig):
    def get_template_directory(self):
        return os.path.join(os.path.dirname(ckan.__file__),
                            "../contrib/alembic")


@click.group(short_help="Scaffolding for regular development tasks.")
def generate():
    """Scaffolding for regular development tasks.
    """
    pass


@generate.command(name='extension', short_help="Create empty extension.")
@click.option('-o',
              '--output-dir',
              help="Location to put the generated "
              "template.",
              default='.')
def extension(output_dir: str):
    """Generate empty extension files to expand CKAN.
    """
    try:
        from cookiecutter.main import cookiecutter
    except ImportError:
        error_shout("`cookiecutter` library is missing from import path.")
        error_shout("Make sure you have dev-dependencies installed:")
        error_shout("\tpip install -r dev-requirements.txt")
        raise click.Abort()

    cur_loc = os.path.dirname(os.path.abspath(__file__))
    os.chdir(cur_loc)
    os.chdir('../../contrib/cookiecutter/ckan_extension/')
    template_loc = os.getcwd()

    # Prompt user for information
    click.echo("\n")
    while True:
        name = click.prompt("Extension's name",
                            default="must begin 'ckanext-'")
        if not name.startswith("ckanext-"):
            error_shout(
                f"ERROR: Project name must start with 'ckanext-' > {name}\n"
                )
        else:
            break

    author = click.prompt("Author's name", default="")
    email = click.prompt("Author's email", default="")
    github = click.prompt("Your Github user or organization name",
                          default="")
    description = click.prompt("Brief description of the project",
                               default="")
    keywords = click.prompt("List of keywords (separated by spaces)",
                            default="CKAN")

    # Ensure one instance of 'CKAN' in keywords
    keywords = ["CKAN"] + [
        k for k in keywords.strip().split() if k.lower() != "ckan"
    ]
    keywords = ' '.join(keywords)

    # Set short name and plugin class name
    project_short = name[8:].lower().replace('-', '_')
    plugin_class_name = project_short.title().replace('_', '') + 'Plugin'

    include_examples = int(click.confirm(
        "Do you want to include code examples?"))
    full_ckan_version: Version = Version(ckan.__version__)
    ckan_version = f"{full_ckan_version.major}.{full_ckan_version.minor}"

    context = {
        "project": name,
        "description": description,
        "author": author,
        "author_email": email,
        "keywords": keywords,
        "github_user_name": github,
        "project_shortname": project_short,
        "plugin_class_name": plugin_class_name,
        "include_examples": include_examples,
        "ckan_version": ckan_version,
        "_source": "cli",
    }

    if output_dir == '.':
        os.chdir('../../../..')
        output_dir = os.getcwd()

    cookiecutter(template_loc, no_input=True, extra_context=context,
                 output_dir=output_dir)

    if not include_examples:
        remove_code_examples(
            os.path.join(
                output_dir, context["project"], "ckanext", project_short))

    click.echo(f"\nWritten: {output_dir}/{name}")


_code_examples = [
    "cli.py",
    "helpers.py",
    "logic",
    "views.py",
    "tests/logic",
    "tests/test_helpers.py",
    "tests/test_views.py",
]


def remove_code_examples(root: str):
    """Remove example files from extension's template.
    """
    for item in _code_examples:
        path = os.path.join(root, item)
        with contextlib.suppress(FileNotFoundError):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)


@generate.command(name='config',
                  short_help='Create a ckan.ini file.')
@click.argument('output_path', nargs=1)
@click.option('-i', '--include-plugin', multiple=True,
              help="Include config declaration from the given plugin")
def make_config(output_path: str, include_plugin: list[str]):
    """Generate a new CKAN configuration ini file."""

    # Output to current directory if no path is specified
    if '/' not in output_path:
        output_path = os.path.join(os.getcwd(), output_path)

    cur_loc = os.path.dirname(os.path.abspath(__file__))
    template_loc = os.path.join(cur_loc, '..', 'config',
                                'deployment.ini_tmpl')

    config_declaration._reset()
    config_declaration.load_core_declaration()
    for plugin in include_plugin:
        config_declaration.load_plugin(plugin)

    variables = {
        "app_main_section": config_declaration.into_ini(
            minimal=False,
            include_docs=False,
        ),
        "default_section": config_declaration.into_ini(
            minimal=False,
            include_docs=True,
            section="DEFAULT"
        )
    }
    with open(template_loc) as file_in:
        template = string.Template(file_in.read())
        try:
            with open(output_path, 'w') as file_out:
                file_out.writelines(template.substitute(variables))
        except OSError as e:
            error_shout(e)
            raise click.Abort()


@generate.command()
@click.option("-p",
              "--plugin",
              help=("Plugin's that requires migration"
                    "(name, used in `ckan.plugins` config section). "
                    "If not provided, core CKAN migration created instead."))
@click.option("-m",
              "--message",
              help="Message string to use with `revision`.")
@click.option(
    "--autogenerate",
    is_flag=True,
    show_default=True,
    default=False,
    help="Populate revision script with candidate migration operations, based"
         " on comparison of database to model.")
def migration(plugin: str, message: str, autogenerate: bool):
    """Create new alembic revision for DB migration.
    """
    if not config:
        error_shout('Config is not loaded')
        raise click.Abort()
    alembic_config = CKANAlembicConfig(_resolve_alembic_config(plugin))
    assert alembic_config.config_file_name
    migration_dir = os.path.dirname(alembic_config.config_file_name)
    alembic_config.set_main_option("sqlalchemy.url", config["sqlalchemy.url"])
    alembic_config.set_main_option('script_location', migration_dir)

    if not os.path.exists(os.path.join(migration_dir, 'script.py.mako')):
        alembic.command.init(alembic_config, migration_dir)

    rev = alembic.command.revision(
        alembic_config, message, autogenerate=autogenerate
    )
    rev_path = rev.path  # type: ignore
    click.secho(
        f"Revision file created. Now, you need to update it: \n\t{rev_path}",
        fg="green")


_factories = {
    "activity": "ckanext.activity.tests.conftest:ActivityFactory",
    "api-token": "ckan.tests.factories:APIToken",
    "dataset": "ckan.tests.factories:Dataset",
    "group": "ckan.tests.factories:Group",
    "organization": "ckan.tests.factories:Organization",
    "resource": "ckan.tests.factories:Resource",
    "resource-view": "ckan.tests.factories:ResourceView",
    "user": "ckan.tests.factories:User",
    "vocabulary": "ckan.tests.factories:Vocabulary",
}


@generate.command(context_settings={
    "allow_extra_args": True, "ignore_unknown_options": True
})
@click.argument(
    "category",
    required=False,
    metavar="[{}|<module.name:Factory>]".format("|".join(_factories))
)
@click.option(
    "-f", "--factory-class",
    help="DEPRECATED. Import path of the factory class")
@click.option("-n", "--fake-count", type=int, default=1,
              help="Number of entities to create")
@click.pass_context
def fake_data(ctx: click.Context, category: str | None,
              factory_class: str | None, fake_count: int):
    """Generate random entities using test factories.

    First argument of this command can be either an import path of a
    factory-class or one of predefined aliases for built-in factories.

    All the extra arguments that follows format `--NAME=VALUE` will be passed
    into the entity factory.

    ..note:: import path was specified using `-f`/`--factory-class` option in
    past. This format is deprecated, because it does not support extra
    arguments

    For instance:

    \b
        ckan generate fake-data dataset
        ckan generate fake-data dataset  --title="My test dataset"
        ckan generate fake-data \\
            ckanext.myext.tests.factories.MyCustomDataset

    All the validation rules still apply. For example, if you have
    `ckan.auth.create_unowned_dataset` config option set to `False`,
    `--owner_org` must be supplied:

    \b
        # use jq to obtain ID of the new organization
        owner_org=$(ckan generate fake-data organization | jq .id -r)
        ckan generate fake-data dataset  --owner_org=$owner_org

    """
    try:
        from ckan.tests.factories import CKANFactory
    except ImportError as e:
        error_shout(e)
        error_shout("Make sure you have dev-dependencies installed:")
        error_shout("\tpip install -r dev-requirements.txt")
        raise click.Abort()

    if factory_class:
        import_path = factory_class
    elif category:
        if category in _factories:
            import_path = _factories[category]
        else:
            import_path = category
    else:
        error_shout("Either `category` or `--factory-class` must be specified")
        raise click.Abort()

    factory = import_string(import_path, silent=True)
    if not factory:
        error_shout(f"{import_path} cannot be imported")
        raise click.Abort()

    if not isinstance(factory, type) or not issubclass(factory, CKANFactory):
        error_shout(f"Factory must be a subclass of `{CKANFactory.__module__}:{CKANFactory.__name__}`")
        raise click.Abort()

    try:
        extras = dict(
            arg[2:].split("=") for arg in ctx.args if arg.startswith("--")
        )
    except ValueError:
        error_shout("Extra arguments must follow the format: --NAME=VALUE")
        raise click.Abort()

    try:
        for entity in factory.create_batch(fake_count, **extras):
            # print entity as json, so that it can be stored in file or passed
            # through jq-pipeline or similar tool
            click.echo(json.dumps(entity))
    except logic.ValidationError as e:
        error_shout(f"Cannot create entity: {e.error_dict}")
        raise click.Abort()
