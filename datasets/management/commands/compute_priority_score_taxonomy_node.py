from django.core.management.base import BaseCommand
from datasets.tasks import compute_gt_taxonomy_node


class Command(BaseCommand):
    help = 'Compute the number of ground truth annotations for ' \
           'all the taxonomy nodes and store it in the database' \
           'This is applied to the fsd dataset'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        compute_gt_taxonomy_node()
