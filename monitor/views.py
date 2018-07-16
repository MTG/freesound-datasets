from django.shortcuts import render, get_object_or_404
from urllib.parse import unquote
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Count
from django.db.models.functions import TruncDay
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from datasets.models import Dataset, User
from monitor.tasks import compute_dataset_top_contributed_categories, compute_dataset_bad_mapping, \
    compute_dataset_difficult_agreement, compute_remaining_annotations_with_duration, \
    compute_dataset_num_contributions_per_day, compute_dataset_num_ground_truth_per_day
from utils.async_tasks import data_from_async_task
from utils.redis_store import DATASET_TOP_CONTRIBUTED_CATEGORIES, DATASET_BAD_MAPPING_CATEGORIES, \
    DATASET_DIFFICULT_AGREEMENT_CATEGORIES, DATASET_REMAINING_CANDIDATE_ANNOTATIONS_PER_CATEGORIES, \
    DATASET_CONTRIBUTIONS_PER_DAY, DATASET_GROUND_TRUTH_PER_DAY


@login_required
def monitor(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))
    top_contributed_categories = data_from_async_task(compute_dataset_top_contributed_categories, [dataset.id], {},
                                                      DATASET_TOP_CONTRIBUTED_CATEGORIES.format(dataset.id), 60)

    bad_mapping_categories = data_from_async_task(compute_dataset_bad_mapping, [dataset.id], {},
                                                  DATASET_BAD_MAPPING_CATEGORIES.format(dataset.id), 60)

    difficult_agreement_categories = data_from_async_task(compute_dataset_difficult_agreement, [dataset.id], {},
                                                          DATASET_DIFFICULT_AGREEMENT_CATEGORIES.format(dataset.id), 60)

    remaining_annotations = data_from_async_task(compute_remaining_annotations_with_duration, [dataset.id], {},
                                                 DATASET_REMAINING_CANDIDATE_ANNOTATIONS_PER_CATEGORIES
                                                 .format(dataset.id), 60)

    num_contributions_per_day = data_from_async_task(compute_dataset_num_contributions_per_day, [dataset.id], {},
                                                     DATASET_CONTRIBUTIONS_PER_DAY.format(dataset.id), 60)

    num_ground_truth_per_day = data_from_async_task(compute_dataset_num_ground_truth_per_day, [dataset.id], {},
                                                    DATASET_GROUND_TRUTH_PER_DAY.format(dataset.id), 60)

    users = User.objects.annotate(num_votes=Count('votes')).filter(num_votes__gt=0)

    return render(request, 'monitor/monitor.html', {'dataset': dataset,
                                                               'top_contributed': top_contributed_categories,
                                                               'bad_mapping': bad_mapping_categories,
                                                               'difficult_agreement': difficult_agreement_categories,
                                                               'remaining_annotations': remaining_annotations,
                                                               'num_contributions_per_day': num_contributions_per_day,
                                                               'num_ground_truth_per_day': num_ground_truth_per_day,
                                                               'users': users})


def monitor_category(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    examples = node.freesound_examples.all()
    verification_examples = node.freesound_examples_verification.all()
    false_verification_examples = node.freesound_false_examples.all()
    return render(request, 'monitor/monitor_category.html', {'dataset': dataset,
                                                             'node': node,
                                                             'examples': examples,
                                                             'verification_examples': verification_examples,
                                                             'false_verification_examples': false_verification_examples})


@login_required
def monitor_user(request, short_name, user_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))
    user = get_object_or_404(User, id=user_id)
    contribs = list(user.votes.filter(candidate_annotation__sound_dataset__dataset=dataset)\
                        .annotate(day=TruncDay('created_at'))\
                        .values('day').annotate(count=Count('id'))\
                        .values_list('day', 'count', 'candidate_annotation__taxonomy_node__name'))
    contribs_failed = list(user.votes.filter(candidate_annotation__sound_dataset__dataset=dataset)\
                               .filter(test='FA')\
                               .annotate(day=TruncDay('created_at'))\
                               .values('day').annotate(count=Count('id'))\
                               .values_list('day', 'count', 'candidate_annotation__taxonomy_node__name'))

    contribs[0] += ('g',)
    for idx, contrib in enumerate(contribs):
        if idx>0:
            if contrib[0] == contribs[idx-1][0]:
                contribs[idx] += (contribs[idx-1][3],)
            else:
                contribs[idx] += ('g',) if contribs[idx-1][3] == 'w' else ('w',)

    if len(contribs_failed) > 0:
        contribs_failed[0] += ('g',)
        for idx, contrib in enumerate(contribs_failed):
            if idx>0:
                if contrib[0] == contribs_failed[idx-1][0]:
                    contribs_failed[idx] += (contribs_failed[idx-1][3],)
                else:
                    contribs_failed[idx] += ('g',) if contribs_failed[idx-1][3] == 'w' else ('w',)

    contribs.reverse()
    contribs_failed.reverse()
    
    return render(request, 'monitor/monitor_user.html', {'dataset': dataset,
                                                         'username': user.username,
                                                         'contribs': contribs,
                                                         'contribs_failed': contribs_failed})


@login_required
def mapping_category(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)

    if request.method == 'POST':
        positive_tags_raw = dict(request.POST).get('positive-tags', '')  # e.g. ['dog, cat', 'dog']
        negative_tags_raw = dict(request.POST).get('negative-tags', '')
        preproc_positive = dict(request.POST).get('preproc-positive', '')
        preproc_negative = dict(request.POST).get('preproc-negative', '')

        positive_tags = [tag.replace(' ', '')
                         for tags in positive_tags_raw
                         for tag in tags.split(',')]  # e.g. [['dog', 'cat'], ['dog']]

        negative_tags = [tag.replace(' ', '')
                         for tags in negative_tags_raw
                         for tag in tags.split(',')]

        results = dataset.retrieve_sound_by_tags(positive_tags, negative_tags, preproc_positive, preproc_negative)
        quality_estimate = dataset.quality_estimate_mapping(results, node_id)

        freesound_ids = results.values_list('freesound_id', flat=True)
        quality_estimate['freesound_ids'] = list(freesound_ids)

        return JsonResponse(quality_estimate)

    elif request.method == 'GET':
        return render(request, 'monitor/mapping_category.html', {
            'dataset': dataset,
            'node': node
        })
