from __future__ import annotations

import click

import ckan.lib.jobs as bg_jobs
import ckan.logic as logic
from ckan.cli import error_shout


@click.group(name="jobs", short_help="Manage background jobs.")
def jobs():
    pass


@jobs.command(short_help="Start a worker.",)
@click.option("--burst", is_flag=True, help="Start worker in burst mode.")
@click.option("--max-idle-time", default=None, type=click.INT,
              help="Max seconds for worker to be idle. "
              "Defaults to None (never stops idling).")
@click.option("--no-scheduler", is_flag=True,
              help="Do not enqueue scheduled jobs from this worker.")
@click.argument("queues", nargs=-1)
def worker(burst: bool, max_idle_time: int, queues: list[str], no_scheduler: bool):
    """Start a worker that fetches jobs from queues and executes them. If
    no queue names are given then the worker listens to the default
    queue, this is equivalent to

        ckan jobs worker default

    If queue names are given then the worker listens to those queues
    and only those:

        ckan jobs worker my-custom-queue

    Hence, if you want the worker to listen to the default queue and
    some others then you must list the default queue explicitly:

        ckan jobs worker default my-custom-queue

    If the `--burst` option is given then the worker will exit as soon
    as all its queues are empty.

    If the `--max-idle-time` option is given then the worker will exit
    after it has been idle for the number of seconds specified.

    If the `--no-scheduler` option is given then this worker will
    not enqueue scheduled jobs. Only one worker will can run as a
    scheduler for each queue so this option may be used on secondary
    workers.
    """
    bg_jobs.Worker(queues).work(
        burst=burst,
        max_idle_time=max_idle_time,
        with_scheduler=not no_scheduler,
    )


@jobs.command(name="list", short_help="List jobs.")
@click.option("-l", "--limit", type=click.INT,
              help="Number of jobs to return. Default: %s" %
              bg_jobs.DEFAULT_JOB_LIST_LIMIT,
              default=bg_jobs.DEFAULT_JOB_LIST_LIMIT)
@click.option("-i", "--ids", is_flag=True, type=click.BOOL,
              help="Only return a list of job ids.", default=False)
@click.argument("queues", nargs=-1)
def list_jobs(queues: list[str],
              limit: int = bg_jobs.DEFAULT_JOB_LIST_LIMIT, ids: bool = False):
    """List currently enqueued jobs from the given queues. If no queue
    names are given then the jobs from all queues are listed.
    """
    data_dict = {
        "queues": list(queues),
        "limit": limit,
        "ids_only": ids,
    }
    jobs = logic.get_action("job_list")({"ignore_auth": True}, data_dict)
    if not jobs:
        return click.secho("There are no pending jobs.", fg="green")
    for job in jobs:
        if ids:
            click.secho(job)
        else:
            if job["title"] is None:
                job["title"] = ""
            else:
                job["title"] = '"{}"'.format(job["title"])
            click.secho("{created} {id} {queue} {title}".format(**job))


@jobs.command(short_help="Show details about a specific job.")
@click.argument("id")
def show(id: str):
    try:
        job = logic.get_action("job_show")(
            {"ignore_auth": True}, {"id": id}
        )
    except logic.NotFound:
        error_shout(f'There is no job with ID "{id}"')
        raise click.Abort()

    click.secho("ID:      {}".format(job["id"]))
    if job["title"] is None:
        title = "None"
    else:
        title = '"{}"'.format(job["title"])
    click.secho(f"Title:   {title}")
    click.secho("Created: {}".format(job["created"]))
    click.secho("Queue:   {}".format(job["queue"]))


@jobs.command(short_help="Cancel a specific job.")
@click.argument("id")
def cancel(id: str):
    """Cancel a specific job. Jobs can only be canceled while they are
    enqueued. Once a worker has started executing a job it cannot be
    aborted anymore.

    """
    try:
        logic.get_action("job_cancel")(
            {"ignore_auth": True}, {"id": id}
        )
    except logic.NotFound:
        error_shout(f'There is no job with ID "{id}"')
        raise click.Abort()

    click.secho(f"Cancelled job {id}", fg="green")


@jobs.command(short_help="Cancel all jobs.")
@click.argument("queues", nargs=-1)
def clear(queues: list[str]):
    """Cancel all jobs on the given queues. If no queue names are given
    then ALL queues are cleared.

    """
    data_dict = {
        "queues": list(queues),
    }
    queues = logic.get_action("job_clear")(
        {"ignore_auth": True}, data_dict
    )
    queues = [f'"{q}"' for q in queues]
    click.secho("Cleared queue(s) {}".format(", ".join(queues)), fg="green")


@jobs.command(short_help="Enqueue a test job.")
@click.argument("queues", nargs=-1)
def test(queues: list[str]):
    """Enqueue a test job. If no queue names are given then the job is
    added to the default queue. If queue names are given then a
    separate test job is added to each of the queues.

    """
    for queue in queues or [bg_jobs.DEFAULT_QUEUE_NAME]:
        job = bg_jobs.enqueue(
            bg_jobs.test_job, ["A test job"], title="A test job", queue=queue
        )
        click.secho(
            f'Added test job {job.id} to queue "{queue}"',
            fg="green",
        )
