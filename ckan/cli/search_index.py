from __future__ import annotations

import multiprocessing as mp
import sys

import click
import sqlalchemy as sa
from ckan.common import config
from ckan.lib.search import query_for
import ckan.logic as logic
import ckan.model as model
from . import error_shout


@click.group(name='search-index', short_help='Search index commands')
@click.help_option('-h', '--help')
def search_index():
    pass


@search_index.command(name='rebuild', short_help='Rebuild search index')
@click.option('-v', '--verbose', is_flag=True)
@click.option('-i', '--force', is_flag=True,
              help='Ignore exceptions when rebuilding the index')
@click.option('-o', '--only-missing',
              help='Index non indexed datasets only', is_flag=True)
@click.option('-q', '--quiet', help='Do not output index rebuild progress',
              is_flag=True)
@click.option('-e', '--commit-each', is_flag=True,
              help='Perform a commit after indexing each dataset. This'
                   'ensures that changes are immediately available on the'
                   'search, but slows significantly the process. Default'
                   'is false.')
@click.option('--keep-orphans', is_flag=True,
              help='Keep orphaned packages in search index after rebuild. '
                   'By default, orphaned packages are automatically cleared.')
@click.argument('package_id', required=False)
@click.pass_context
def rebuild(
        ctx: click.Context, verbose: bool, force: bool, only_missing: bool,
        quiet: bool, commit_each: bool, keep_orphans: bool, package_id: str
):
    ''' Rebuild search index '''
    errors = 0
    from ckan.lib.search import rebuild, commit
    try:

        rebuild(package_id,
                only_missing=only_missing,
                force=force,
                defer_commit=(not commit_each),
                quiet=quiet and not verbose,
                clear=False)  # Never clear before rebuild

        if not keep_orphans:
            ctx.invoke(clear_orphans)

    except logic.NotFound:
        error_shout("Couldn't find package %s" % package_id)
        errors = 1
    except Exception as e:
        error_shout(e)
        errors = 1
    if not commit_each:
        commit()
    if errors:
        sys.exit(errors)


@search_index.command(name='check', short_help='Check search index')
def check():
    from ckan.lib.search import check
    check()


@search_index.command(name='show', short_help='Show index of a dataset')
@click.argument('dataset_name')
def show(dataset_name: str):
    from ckan.lib.search import show

    index = show(dataset_name)
    click.echo(index)


@search_index.command(name='clear', short_help='Clear the search index')
@click.argument('dataset_name', required=False)
def clear(dataset_name: str):
    from ckan.lib.search import clear, clear_all

    if dataset_name:
        clear(dataset_name)
    else:
        clear_all()


def get_orphans() -> list[str]:
    search = None
    indexed_package_ids = []
    while search is None or len(indexed_package_ids) < search['count']:
        search = logic.get_action('package_search')({"ignore_auth":True}, {
            'q': '*:*',
            'fl': 'id',
            'start': len(indexed_package_ids),
            'rows': 1000})
        indexed_package_ids += search['results']

    package_ids = {r[0] for r in model.Session.query(model.Package.id)}

    orphaned_package_ids = []

    for indexed_package_id in indexed_package_ids:
        if indexed_package_id['id'] not in package_ids:
            orphaned_package_ids.append(indexed_package_id['id'])

    return orphaned_package_ids


@search_index.command(
    name='list-orphans',
    short_help='Lists any non-existent packages in the search index'
)
def list_orphans_command():
    orphaned_package_ids = get_orphans()
    if len(orphaned_package_ids):
        click.echo(orphaned_package_ids)
    click.echo(f"Found {len(orphaned_package_ids)} orphaned package(s).")


@search_index.command(
    name='clear-orphans',
    short_help='Clear any non-existent packages in the search index'
)
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def clear_orphans(ctx: click.Context, verbose: bool = False):
    for orphaned_package_id in get_orphans():
        if verbose:
            click.echo(f"Clearing search index for dataset {orphaned_package_id}...")
        ctx.invoke(clear, dataset_name=orphaned_package_id)


@search_index.command(
    name='list-unindexed',
    short_help='Lists any missing packages from the search index'
)
def list_unindexed():
    packages = model.Session.query(model.Package.id)
    if config.get('ckan.search.remove_deleted_packages'):
        packages = packages.filter(model.Package.state != 'deleted')

    package_ids = [r[0] for r in packages.all()]

    package_query = query_for(model.Package)
    indexed_pkg_ids = set(package_query.get_all_entity_ids(
        max_results=len(package_ids)))
    # Packages not indexed
    unindexed_package_ids = set(package_ids) - indexed_pkg_ids

    if len(unindexed_package_ids):
        click.echo(unindexed_package_ids)
    click.echo(f"Found {len(unindexed_package_ids)} unindexed package(s).")


@search_index.command(name='rebuild-fast',
                      short_help='Reindex with multiprocessing')
def rebuild_fast():
    from ckan.lib.search import commit

    db_url = config['sqlalchemy.url']
    engine = sa.create_engine(db_url)
    package_ids = []
    with engine.connect() as conn:
        result = conn.execute(
            sa.text("SELECT id FROM package where state = 'active'")
        )
    for row in result:
        package_ids.append(row[0])

    def start(ids: list[str]):
        from ckan.lib.search import rebuild
        rebuild(package_ids=ids)

    def chunks(list_: list[str], n: int):
        """ Yield n successive chunks from list_"""
        newn = int(len(list_) / n)
        for i in range(0, n - 1):
            yield list_[i * newn:i * newn + newn]
        yield list_[n * newn - newn:]

    processes = []

    try:
        for chunk in chunks(package_ids, mp.cpu_count()):
            process = mp.Process(target=start, args=(chunk,))
            processes.append(process)
            process.daemon = True
            process.start()

        for process in processes:
            process.join()
        commit()
    except Exception as e:
        error_shout(e)
