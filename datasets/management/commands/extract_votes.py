from django.core.management.base import BaseCommand
from django.conf import settings
import json
import os
from datasets.models import CandidateAnnotation, Vote, TaxonomyNode, Dataset


class Command(BaseCommand):
    help = 'Extract user votes' \
           'Usage: python manage.py extract_votes <dataset_shor_name> <output_file>'

    def add_arguments(self, parser):
        parser.add_argument('dataset_short_name', type=str)
        parser.add_argument('output_file', type=str)

    def handle(self, *args, **options):
        dataset_short_name = options['dataset_short_name']
        output_file = options['output_file']

        dataset = Dataset.objects.get(short_name=dataset_short_name)
        nodes = TaxonomyNode.objects.all()
        votes_dict = {node_id: {'PP': list(),
                                'PNP': list(),
                                'NP': list(),
                                'U': list(),
                                'candidates': list()} for node_id in nodes.values_list('node_id', flat=True)}
        vote_value_to_letter = {1: 'PP', 0.5: 'PNP', -1: 'NP', 0: 'U'}

        votes_with_info = Vote.objects.filter(candidate_annotation__sound_dataset__dataset=dataset)\
            .values('vote', 'candidate_annotation__taxonomy_node__node_id',
                    'candidate_annotation__sound_dataset__sound__freesound_id')
        candidate_annotations = CandidateAnnotation.objects.filter(sound_dataset__dataset=dataset)\
            .values('taxonomy_node__node_id', 'sound_dataset__sound__freesound_id')

        for vote in votes_with_info:
            votes_dict[vote['candidate_annotation__taxonomy_node__node_id']]\
                [vote_value_to_letter[vote['vote']]]\
                .append(vote['candidate_annotation__sound_dataset__sound__freesound_id'])

        for candidate_annotation in candidate_annotations:
            votes_dict[candidate_annotation['taxonomy_node__node_id']]['candidates']\
                .append(candidate_annotation['sound_dataset__sound__freesound_id'])

        json.dump(votes_dict, open(os.path.join(settings.DATASET_RELEASE_FILES_FOLDER,
                                                '{0}.json'.format(output_file)), 'w'))
