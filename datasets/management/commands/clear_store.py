from django.core.management.base import BaseCommand
from utils.redis_store import store


class Command(BaseCommand):
    help = 'Remove all keys stored in Redis Store. Use it as python manage.py clear_store'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        count = store.delete_keys()
        print('Deleted {0} keys'.format(count))