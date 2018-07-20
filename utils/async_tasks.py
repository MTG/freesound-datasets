from utils.redis_store import store
from celery.signals import task_postrun, task_prerun


def data_from_async_task(task_func, task_args, task_kwargs, store_key, refresh_time=60, run_once=True):

    # Get task results previously stored in store
    output, elapsed_time = store.get(store_key, include_elapsed_time=True)

    # If there are no previously stored results (elapsed_time will be a magically big number) or
    # if the previously stored results are older than refresh_time, then we trigger recompute of the
    # task so that results are ready for next load.
    # If run_once=True, we only trigger the recompute if the task is not already running
    if elapsed_time > refresh_time:
        if run_once:
            # Check that it is not already running
            computing_store_key = 'computing-{0}.{1}'.format(task_func.__module__, task_func.__name__)
            if store.get(computing_store_key):
                # Task is already running, don't trigger running again
                print('Skip computing data for {0}, already running'.format(store_key))
                return output
        task_func.delay(store_key, *task_args, **task_kwargs)
    return output


@task_prerun.connect()
def task_prerun(signal=None, sender=None, task_id=None, task=None, args=None, **kwargs):
    # Set computing key
    computing_store_key = 'computing-{0}'.format(task.name)
    store.set(computing_store_key, {'running': True})


@task_postrun.connect()
def task_postrun(signal=None, sender=None, task_id=None, task=None, retval=None, state=None, args=None, **kwargs):
    # Delete computing key (if present)
    computing_store_key = 'computing-{0}'.format(task.name)
    store.delete(computing_store_key)
