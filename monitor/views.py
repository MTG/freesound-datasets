from django.shortcuts import render, get_object_or_404
from urllib.parse import unquote
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDay
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from datasets.models import Dataset, User, CandidateAnnotation
from datasets.utils import stem
from datasets.templatetags.general_templatetags import sound_player
from monitor.tasks import compute_dataset_top_contributed_categories, compute_dataset_bad_mapping, \
    compute_dataset_difficult_agreement, compute_remaining_annotations_with_duration, \
    compute_dataset_num_contributions_per_day, compute_dataset_num_ground_truth_per_day
from utils.async_tasks import data_from_async_task
from utils.redis_store import DATASET_TOP_CONTRIBUTED_CATEGORIES, DATASET_BAD_MAPPING_CATEGORIES, \
    DATASET_DIFFICULT_AGREEMENT_CATEGORIES, DATASET_REMAINING_CANDIDATE_ANNOTATIONS_PER_CATEGORIES, \
    DATASET_CONTRIBUTIONS_PER_DAY, DATASET_GROUND_TRUTH_PER_DAY
from random import shuffle


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
    contribs = list(user.votes.filter(candidate_annotation__sound_dataset__dataset=dataset)
                        .annotate(day=TruncDay('created_at'))
                        .order_by("-day")
                        .values('day').annotate(count=Count('id'))
                        .values_list('day', 'count', 'candidate_annotation__taxonomy_node__name'))
    contribs_failed = list(user.votes.filter(candidate_annotation__sound_dataset__dataset=dataset)
                               .filter(test='FA')
                               .annotate(day=TruncDay('created_at'))
                               .order_by("-day")
                               .values('day').annotate(count=Count('id'))
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
        run_or_submit = dict(request.POST).get('run-or-submit', ['run'])[0]

        positive_tags_raw = dict(request.POST).get('positive-tags', '')  # e.g. ['dog, cat', 'dog']
        negative_tags_raw = dict(request.POST).get('negative-tags', '')
        preproc_positive = True if dict(request.POST).get('preproc-positive', ['true']) == ['true'] else False
        preproc_negative = True if dict(request.POST).get('preproc-negative', ['false']) == ['true'] else False

        positive_tags = [[stem(tag.replace(' ', '').lower()) if preproc_positive else tag.replace(' ', '').lower()
                          for tag in tags.split(',')]
                         for tags in positive_tags_raw if tags != '']  # e.g. [['dog', 'cat'], ['dog']]

        negative_tags = [stem(tag.replace(' ', '')).lower() if preproc_negative else tag.replace(' ', '').lower()
                         for tags in negative_tags_raw
                         for tag in tags.split(',') if tags != '']

        results = dataset.retrieve_sound_by_tags(positive_tags, negative_tags, preproc_positive, preproc_negative)
        candidates = list(node.candidate_annotations.values_list('sound_dataset__sound__freesound_id', flat=True))

        # Run the mapping strategy and return the retrieved sounds and some statistics
        if run_or_submit == 'run':
            quality_estimate = dataset.quality_estimate_mapping(results, node_id)
            freesound_ids = list(results.values_list('freesound_id', flat=True))
            shuffle(freesound_ids)
            quality_estimate['freesound_ids'] = freesound_ids
            quality_estimate['num_sounds'] = len(freesound_ids)
            num_common_sounds = len(list(set(candidates).intersection(set(freesound_ids))))

            stats = {
                'retrieved': quality_estimate,
                'mapping': node.quality_estimate,
                'num_common_sounds': num_common_sounds
            }
            return JsonResponse(stats)

        # Submit the retrieved sounds
        elif run_or_submit == 'submit':
            freesound_ids_str = dict(request.POST).get('freesound-ids', [None])[0]

            # Retrieved by Freesound IDs
            if freesound_ids_str:
                freesound_ids = freesound_ids_str.split(',')
                results = dataset.sounds.filter(freesound_id__in=freesound_ids)
                new_sounds = results.exclude(freesound_id__in=candidates)
                num_new_sounds = new_sounds.count()
                try:
                    with transaction.atomic():
                        for sound in new_sounds:
                            CandidateAnnotation.objects.create(
                                sound_dataset=sound.sounddataset_set.filter(dataset=dataset).first(),
                                type='MA',
                                algorithm='platform_manual: By Freesound ID',
                                taxonomy_node=node,
                                created_by=request.user
                            )
                except:
                    return JsonResponse({'error': True})

                return JsonResponse({'error': False,
                                     'num_candidates_added': num_new_sounds,
                                     'num_candidates_deleted': 0})

            # Retrieved by the tag based query
            else:
                add_or_replace = dict(request.POST).get('add-or-replace', ['add'])[0]
                voted_negative = dict(request.POST).get('voted-negative', [])
                results = results.exclude(freesound_id__in=voted_negative)
                name_algorithm = str(positive_tags) + ' AND NOT ' + str(negative_tags)
                num_new_sounds = 0
                num_deleted = 0

                # Add the new candidates to the existing ones
                if add_or_replace == 'add':
                    new_sounds = results.exclude(freesound_id__in=candidates)
                    num_new_sounds = new_sounds.count()
                    try:
                        with transaction.atomic():
                            for sound in new_sounds:
                                CandidateAnnotation.objects.create(
                                    sound_dataset=sound.sounddataset_set.filter(dataset=dataset).first(),
                                    type='AU',
                                    algorithm='platform_mapping: {}'.format(name_algorithm),
                                    taxonomy_node=node,
                                    created_by=request.user
                                )
                    except:
                        return JsonResponse({'error': True})

                # Replace the actual candidates with the retrieved ones (deletes only candidates never voted)
                elif add_or_replace == 'replace':
                    try:
                        with transaction.atomic():
                            new_sounds = results.exclude(freesound_id__in=candidates)
                            num_deleted = node.candidate_annotations.exclude(sound_dataset__sound__in=results)\
                                                                    .annotate(num_votes=Count('votes'))\
                                                                    .filter(num_votes=0)\
                                                                    .delete()[0]
                            num_new_sounds = new_sounds.count()
                            for sound in new_sounds:
                                CandidateAnnotation.objects.create(
                                    sound_dataset=sound.sounddataset_set.filter(dataset=dataset).first(),
                                    type='AU',
                                    algorithm='platform_mapping: {}'.format(name_algorithm),
                                    taxonomy_node=node,
                                    created_by=request.user
                                )
                    except:
                        return JsonResponse({'error': True})

                return JsonResponse({'error': False,
                                     'num_candidates_added': num_new_sounds,
                                     'num_candidates_deleted': num_deleted})

    elif request.method == 'GET':
        mapping_rule = [dataset.taxonomy.data[node_id].get('fs_tags', ''),
                        dataset.taxonomy.data[node_id].get('omit_fs_tags', '')]
        platform_mapping_rules = list(set(node.candidate_annotations.exclude(type='MA')
                                          .values_list('algorithm', flat=True)))
        platform_mapping_rules.remove('tag_matching_mtg_1')
        platform_mapping_rules_formated = [(m.split(' AND NOT ')[0].split('platform_mapping: ')[1],
                                            m.split(' AND NOT ')[1])
                                           for m in platform_mapping_rules]
        return render(request, 'monitor/mapping_category.html', {
            'dataset': dataset,
            'node': node,
            'mapping_rule': mapping_rule,
            'platform_mapping_rules': platform_mapping_rules_formated
        })


def player(request, short_name, freesound_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    context = sound_player(dataset, freesound_id, 'small')
    return render(request, 'datasets/player.html', context)
