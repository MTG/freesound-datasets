from django.core.management.base import BaseCommand
from datasets.tasks import compute_priority_score_candidate_annotations


class Command(BaseCommand):
    help = 'Compute the priority score for all the candidate annotations' \
           'and store it in the database. This is applied to the fsd dataset'
    
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        compute_priority_score_candidate_annotations()
