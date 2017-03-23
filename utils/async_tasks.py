from utils.redis_store import store


def data_from_async_task(task_func, task_args, task_kwargs, store_key, refresh_time=60):
    # Get task results previously stored in store
    output, elapsed_time = store.get(store_key, include_elapsed_time=True)

    # If there are no previously stored results (elapsed_time will be a magically big number) or
    # if the previously stored results are older than refresh_time, then we trigger recompute of the
    # task so that results are ready for next load.
    if elapsed_time > refresh_time:
        task_func.delay(store_key, *task_args,  **task_kwargs)
    return output
