from django.core.management.base import BaseCommand
from datasets.models import *
import json


class Command(BaseCommand):
    help = 'Propagate ground truth annotations. Use it as python manage.py propagate_ground_truth_annotations'

    def handle(self, *args, **options):
        for annotation in GroundTruthAnnotation.objects.all():
            annotation.propagate_annotation()

