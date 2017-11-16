from django.core.management.base import BaseCommand
from datasets.models import *
import json


class Command(BaseCommand):
    help = 'Remove annotations associated with audio clips having a children from which it propagates its ground truth'\
           'Use it as python manage.py remove_non_leaf_annotations DATASET_ID'

    class ProgressBar:
        """
        Progress bar
        """
        def __init__(self, valmax, maxbar, title):
            if valmax == 0:  valmax = 1
            if maxbar > 200: maxbar = 200
            self.valmax = valmax
            self.maxbar = maxbar
            self.title = title
            print ('')

        def update(self, val):
            import sys
            # format
            if val > self.valmax: val = self.valmax

            # process
            perc = round((float(val) / float(self.valmax)) * 100)
            scale = 100.0 / float(self.maxbar)
            bar = int(perc / scale)

            # render
            out = '\r %20s [%s%s] %3d / %3d' % (self.title, '=' * bar, ' ' * (self.maxbar - bar), val, self.valmax)
            sys.stdout.write(out)
            sys.stdout.flush()

    def add_arguments(self, parser):
        parser.add_argument('dataset_id', type=int)

    def handle(self, *args, **options):
        dataset_id = options['dataset_id']
        dataset = Dataset.objects.get(id=dataset_id)
        taxonomy = dataset.taxonomy

        # find annotations that should be removed (having an annotation that correspond to a children which propagate)
        taxonomy_nodes = dataset.taxonomy.taxonomynode_set.all()
        bar = self.ProgressBar(len(taxonomy_nodes), 30, 'Processing...')
        bar.update(0)
        annotations_to_remove = []
        for idx, node in enumerate(taxonomy_nodes):
            bar.update(idx+1)
            children_node = taxonomy.get_all_propagate_from_children(node.node_id)
            for annotation in CandidateAnnotation.objects.filter(taxonomy_node=node):
                if CandidateAnnotation.objects.filter(taxonomy_node__in=children_node,
                                             sound_dataset__sound=annotation.sound_dataset.sound).count() > 0:
                    annotations_to_remove.append(annotation)

        # remove only the annotations that have no vote
        annotations_id_to_remove = [a.id for a in annotations_to_remove if a.votes.all().count() == 0]
        CandidateAnnotation.objects.filter(id__in=annotations_id_to_remove).delete()

        print('\n')
        print('{0} annotations where deleted'.format(len(annotations_id_to_remove)))
