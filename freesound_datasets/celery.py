from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freesound_datasets.settings')

app = Celery('freesound_datasets')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
app.autodiscover_tasks('datasets', related_name='tasks')


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


@app.task(bind=True)
def run_django_management_command(self, command, *args, **kwargs):
    print('holy moly, it works!')
    #management.call_command(command, *args, **kwargs)


# Configure periodic tasks here
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour="*", minute="*/2"),
        run_django_management_command.s('renew_access_tokens'),
name='Renew expired tokens')
