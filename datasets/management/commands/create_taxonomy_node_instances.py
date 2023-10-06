from django.core.management.base import BaseCommand
from datasets.models import Taxonomy, TaxonomyNode


class Command(BaseCommand):
    help = 'Creates the taxonomy node instances from the information in the taxonomy json field' \
            'Use it as python manage.py create_taxonomy_node_instances TAXONOMY_ID'

    def add_arguments(self, parser):
        parser.add_argument('taxonomy_id', type=int)

    def handle(self, *args, **options):
        taxonomy_id = options['taxonomy_id']
        taxonomy = Taxonomy.objects.get(id=taxonomy_id)

        # loop for creating taxonomy node instances 
        for node_id, node in taxonomy.data.items():
            abstract = 'abstract' in node.get('restrictions', [])
            omitted = 'omittedTT' in node.get('restrictions', [])
            taxonomy_node =  TaxonomyNode.objects.create(node_id=node_id, 
                                                         name=node['name'], 
                                                         description=node.get('description', ''), 
                                                         citation_uri=node.get('citation_uri', ''), 
                                                         abstract=abstract,
                                                         omitted=omitted, 
                                                         taxonomy=taxonomy)

            # loop for adding parent relations
            all_taxonomy_nodes = taxonomy.taxonomynode_set.all()
            for taxonomy_node in all_taxonomy_nodes:
                if 'parent_ids' in taxonomy.data[taxonomy_node.node_id]:
                    for node_id in taxonomy.data[taxonomy_node.node_id]['parent_ids']:
                        parent_node = TaxonomyNode.objects.get(node_id=node_id)
                        taxonomy_node.parents.add(parent_node)
