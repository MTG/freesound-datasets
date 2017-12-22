from django.core.management.base import BaseCommand
from datasets.models import User


class Command(BaseCommand):
    help = 'Transfer the votes of an user to another' \
           'Usage: python manage.py transfer_user_votes <from_username> <to_username>'

    def add_arguments(self, parser):
        parser.add_argument('from_username', type=str)
        parser.add_argument('to_username', type=str)

    def handle(self, *args, **options):
        from_username = options['from_username']
        to_username = options['to_username']
        from_user = User.objects.get(username=from_username)
        to_user = User.objects.get(username=to_username)

        for vote in from_user.votes.all():
            vote.created_by = to_user
            vote.save()
