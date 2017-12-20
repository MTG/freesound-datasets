from datasets.models import Dataset, Vote
from celery import shared_task
from utils.redis_store import store
import logging


logger = logging.getLogger('tasks')


@shared_task
def compute_dataset_top_contributed_categories(store_key, dataset_id, N=15):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        nodes = dataset.taxonomy.taxonomynode_set.all()
        top_categories = list()
        for node in nodes:
            num_votes = Vote.objects.filter(candidate_annotation__taxonomy_node=node).count()
            top_categories.append((node.name, num_votes))

        top_categories = sorted(top_categories, key=lambda x: x[1], reverse=True)  # Sort by number of votes

        store.set(store_key, {'top_categories': top_categories[:N]})
        logger.info('Finished computing data for {0}'.format(store_key))
    except Dataset.DoesNotExist:
        pass
