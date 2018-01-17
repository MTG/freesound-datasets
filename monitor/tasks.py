from datasets.models import Dataset, Vote
from celery import shared_task
from utils.redis_store import store
from statistics import mean, StatisticsError
from django.db.models.functions import TruncDay
from django.db.models import Count
import json
import logging
import datetime


logger = logging.getLogger('tasks')


@shared_task
def compute_dataset_top_contributed_categories(store_key, dataset_id, N=15):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        nodes = dataset.taxonomy.taxonomynode_set.all()
        reference_date = datetime.datetime.today() - datetime.timedelta(days=7)
        top_categories = list()
        top_categories_last_week = list()

        for node in nodes:
            num_votes = Vote.objects.filter(candidate_annotation__taxonomy_node=node).count()
            top_categories.append((node.url_id, node.name, num_votes, node.omitted))
            num_votes_last_week = Vote.objects.filter(candidate_annotation__taxonomy_node=node, created_at__gt=reference_date).count()
            top_categories_last_week.append((node.url_id, node.name, num_votes_last_week, node.omitted))

        top_categories = sorted(top_categories, key=lambda x: x[2], reverse=True)  # Sort by number of votes
        top_categories_last_week = sorted(top_categories_last_week, key=lambda x: x[2], reverse=True)

        store.set(store_key, {'top_categories': top_categories[:N],
                              'top_categories_last_week': top_categories_last_week[:N]})

        logger.info('Finished computing data for {0}'.format(store_key))

    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_dataset_bad_mapping(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        nodes = dataset.taxonomy.taxonomynode_set.all()
        reference_date = datetime.datetime.today() - datetime.timedelta(days=31)
        bad_mapping_categories = list()
        bad_mapping_categories_last_month = list()

        for node in nodes:
            num_PP = dataset.num_votes_with_value(node.node_id, 1.0)
            num_PNP = dataset.num_votes_with_value(node.node_id, 0.5)
            num_NP = dataset.num_votes_with_value(node.node_id, -1.0)
            num_U = dataset.num_votes_with_value(node.node_id, 0.0)
            try:
                bad_mapping_score = (num_NP + num_U) / (num_PP + num_PNP + num_NP + num_U)
            except ZeroDivisionError:
                bad_mapping_score = 0

            num_PP_last_month = dataset.num_votes_with_value_after_date(node.node_id, 1.0, reference_date)
            num_PNP_last_month = dataset.num_votes_with_value_after_date(node.node_id, 0.5, reference_date)
            num_NP_last_month = dataset.num_votes_with_value_after_date(node.node_id, -1.0, reference_date)
            num_U_last_month = dataset.num_votes_with_value_after_date(node.node_id, 0.0, reference_date)
            try:
                bad_mapping_score_last_month = (num_NP_last_month + num_U_last_month) / \
                                               (num_PP_last_month + num_PNP_last_month + num_NP_last_month + num_U_last_month)
            except ZeroDivisionError:
                bad_mapping_score_last_month = 0

            bad_mapping_categories.append((node.url_id, node.name, bad_mapping_score, node.omitted))
            bad_mapping_categories_last_month.append((node.url_id, node.name, bad_mapping_score_last_month, node.omitted))

            bad_mapping_categories = sorted(bad_mapping_categories, key=lambda x: x[2], reverse=True)  # Sort by mapping score
            bad_mapping_categories = [category_name_score for category_name_score in bad_mapping_categories  # keep bad ones
                                      if category_name_score[2] >= 0.5]

            bad_mapping_categories_last_month = sorted(bad_mapping_categories_last_month, key=lambda x: x[2], reverse=True)
            bad_mapping_categories_last_month = [category_name_score for category_name_score in bad_mapping_categories_last_month
                                                 if category_name_score[2] >= 0.5]

        store.set(store_key, {'bad_mapping_categories': bad_mapping_categories,
                              'bad_mapping_categories_last_month': bad_mapping_categories_last_month})

        logger.info('Finished computing data for {0}'.format(store_key))

    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_dataset_difficult_agreement(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        nodes = dataset.taxonomy.taxonomynode_set.all()
        reference_date = datetime.datetime.today() - datetime.timedelta(days=31)
        difficult_agreement_categories = list()
        difficult_agreement_categories_last_month = list()

        for node in nodes:
            ground_truth_annotations = node.ground_truth_annotations.filter(from_propagation=False)
            ground_truth_annotations_last_month = node.ground_truth_annotations.filter(from_propagation=False,
                                                                                       created_at__gt=reference_date)
            try:
                mean_votes_agreement = mean([annotation.from_candidate_annotation.votes.count()
                                             for annotation in ground_truth_annotations])
            except StatisticsError:
                mean_votes_agreement = 0
            try:
                mean_votes_agreement_last_month = mean([annotation.from_candidate_annotation.votes.count()
                                                        for annotation in ground_truth_annotations_last_month])
            except StatisticsError:
                mean_votes_agreement_last_month = 0

            difficult_agreement_categories.append((node.url_id, node.name, mean_votes_agreement, node.omitted))
            difficult_agreement_categories_last_month.append((node.url_id, node.name, mean_votes_agreement_last_month, node.omitted))

        difficult_agreement_categories = [category_name_votes for category_name_votes in difficult_agreement_categories
                                          if category_name_votes[2] > 2]
        difficult_agreement_categories = sorted(difficult_agreement_categories, key=lambda x: x[2], reverse=True)
        difficult_agreement_categories_last_month = [category_name_votes for category_name_votes
                                                     in difficult_agreement_categories_last_month
                                                     if category_name_votes[2] > 2]
        difficult_agreement_categories_last_month = sorted(difficult_agreement_categories_last_month, key=lambda x: x[2]
                                                           , reverse=True)

        store.set(store_key, {'difficult_agreement_categories': difficult_agreement_categories,
                              'difficult_agreement_categories_last_month': difficult_agreement_categories_last_month})

        logger.info('Finished computing data for {0}'.format(store_key))

    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_remaining_annotations_with_duration(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        nodes = dataset.taxonomy.taxonomynode_set.all()
        remaining_categories = list()

        for node in nodes:
            non_gt_annotations = dataset.non_ground_truth_annotations_per_taxonomy_node(node.node_id)
            num_candidate_annotations_non_gt = non_gt_annotations.count()
            num_candidate_annotations_non_gt_max_10_sec = non_gt_annotations.\
                filter(sound_dataset__sound__extra_data__duration__lte=10).count()
            num_candidate_annotations_non_gt_max_20_sec = non_gt_annotations.\
                filter(sound_dataset__sound__extra_data__duration__lte=20,
                       sound_dataset__sound__extra_data__duration__gt=10).count()
            remaining_categories.append((node.url_id, node.name, num_candidate_annotations_non_gt,
                                         num_candidate_annotations_non_gt_max_10_sec,
                                         num_candidate_annotations_non_gt_max_20_sec,
                                         node.omitted))

        remaining_categories = sorted(remaining_categories, key=lambda x: x[3])

        store.set(store_key, {'remaining_categories': remaining_categories})

        logger.info('Finished computing data for {0}'.format(store_key))

    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_dataset_num_contributions_per_day(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        contribution_per_day = Vote.objects\
            .filter(candidate_annotation__sound_dataset__dataset=dataset)\
            .annotate(day=TruncDay('created_at'))\
            .values('day')\
            .annotate(count=Count('id'))\
            .values('day', 'count')

        store.set(store_key, {'contribution_per_day': json.dumps([{
            'day': str(entry['day']),
            'count':entry['count']}
            for entry in contribution_per_day])})

        logger.info('Finished computing data for {0}'.format(store_key))

    except Dataset.DoesNotExist:
        pass
