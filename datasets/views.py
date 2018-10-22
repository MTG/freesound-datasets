from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote, quote
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity, TrigramDistance
from django.conf import settings
from django.urls import reverse
from django.db.models import Count, F, Q
from django.db import transaction, connection
from django.forms import formset_factory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datasets.models import Dataset, DatasetRelease, CandidateAnnotation, Vote, TaxonomyNode, SoundDataset, Sound, User
from datasets import utils
from django.utils import timezone
from datasets.forms import DatasetReleaseForm, PresentNotPresentUnsureForm, CategoryCommentForm
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from datasets.tasks import generate_release_index, compute_dataset_basic_stats, compute_dataset_taxonomy_stats, \
    compute_annotators_ranking, compute_taxonomy_tree
from utils.redis_store import store, DATASET_BASIC_STATS_KEY_TEMPLATE, DATASET_TAXONOMY_STATS_KEY_TEMPLATE, \
    DATASET_ANNOTATORS_RANKING_TEMPLATE, FSD_TAXONOMY_TREE
from utils.async_tasks import data_from_async_task
import os
import random
import json
import datetime


#######################
# EXPLORE DATASET VIEWS
#######################

def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    random_taxonomy_nodes = dataset.get_random_taxonomy_node_with_examples()

    # Get previously stored dataset release stats
    dataset_basic_stats = data_from_async_task(compute_dataset_basic_stats, [dataset.id], {},
                                               DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), 60)

    return render(request, 'datasets/dataset.html', {
        'dataset': dataset,
        'dataset_page': True,
        'user_is_maintainer': user_is_maintainer,
        'random_nodes': random_taxonomy_nodes,
        'dataset_basic_stats': dataset_basic_stats,
    })


def dataset_explore(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    form_errors = False
    if request.method == 'POST':
        form = DatasetReleaseForm(request.POST)
        if form.is_valid():
            dataset_release = form.save(commit=False)
            dataset_release.dataset = dataset
            dataset_release.save()
            async_job = generate_release_index.delay(dataset.id, dataset_release.id,
                                                     form.cleaned_data['max_number_of_sounds'])
            form = DatasetReleaseForm()  # Reset form
        else:
            form_errors = True
    else:
        form = DatasetReleaseForm()

    return render(request, 'datasets/dataset_explore.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'dataset_release_form': form,
        'dataset_release_form_errors': form_errors,
    })


def dataset_taxonomy_tree(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    taxonomy_tree = data_from_async_task(compute_taxonomy_tree, [], {},
                                         FSD_TAXONOMY_TREE, refresh_time=3600)
    if not taxonomy_tree:
        taxonomy_tree = dataset.taxonomy.get_taxonomy_as_tree()

    return JsonResponse(taxonomy_tree)


def dataset_taxonomy_table(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)

    # Get request info to chose which button to place per category
    category_link_to = {
        'e': ('dataset-explore-taxonomy-node', 'Explore'),
        'cva': ('contribute-validate-annotations-category', 'Choose'),
    }[request.GET.get('link_to', 'e')]

    # Get previously stored dataset taxonomy stats
    dataset_taxonomy_stats = data_from_async_task(compute_dataset_taxonomy_stats, [dataset.id], {},
                                                  DATASET_TAXONOMY_STATS_KEY_TEMPLATE.format(dataset.id), 60)

    return render(request, 'datasets/dataset_taxonomy_table.html', {
        'dataset': dataset,
        'category_link_to': category_link_to,
        'dataset_taxonomy_stats': dataset_taxonomy_stats})


# old view, not used anymore
def dataset_releases_table(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    if user_is_maintainer:
        dataset_releases_for_user = dataset.releases
    else:
        dataset_releases_for_user = dataset.releases.filter(type="PU")  # Only get public releases

    # Get previously stored dataset release stats
    dataset_basic_stats = data_from_async_task(compute_dataset_basic_stats, [dataset.id], {},
                                               DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), 60)

    return render(request, 'datasets/dataset_release_table.html', {
        'dataset': dataset,
        'dataset_basic_stats': dataset_basic_stats,
        'user_is_maintainer': user_is_maintainer,
        'dataset_releases_for_user': dataset_releases_for_user
    })


def dataset_state_table(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)

    # Get previously stored dataset release stats
    dataset_basic_stats = data_from_async_task(compute_dataset_basic_stats, [dataset.id], {},
                                               DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), 60)

    return render(request, 'datasets/dataset_state_table.html', {
        'dataset': dataset,
        'dataset_basic_stats': dataset_basic_stats,
        'user_is_maintainer': user_is_maintainer,
    })


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    annotation_list = dataset.annotations_per_taxonomy_node(node_id)\
        .annotate(num_votes=Count('votes')).order_by('-num_votes', 'pk')
    paginator = Paginator(annotation_list, 10)
    page = request.GET.get('page')
    try:
        annotations = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        annotations = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        annotations = paginator.page(paginator.num_pages)

    return render(request, 'datasets/taxonomy_node.html', {'dataset': dataset, 'node': node,
                                                           'user_is_maintainer': user_is_maintainer,
                                                           'sounds': annotations})


def explore_taxonomy(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'datasets/explore_taxonomy.html', {
        'dataset': dataset
    })


def search_taxonomy_node(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed
    taxonomy = dataset.taxonomy
    query = request.GET.get('q', '')

    # vector = SearchVector('name', weight='A') + SearchVector('description', weight='C')
    # query = SearchQuery(query)
    # qs_results = TaxonomyNode.objects.filter(taxonomy__dataset=dataset)\
    #                                  .annotate(rank=SearchRank(vector, query)).filter(rank__gte=0.3)\
    #                                  .order_by('rank')

    qs_results = TaxonomyNode.objects.filter(taxonomy__dataset=dataset)\
                                     .annotate(similarity=TrigramSimilarity('name', query) +
                                                          TrigramSimilarity('description', query),)\
                                     .filter(similarity__gte=0.2)\
                                     .order_by('-similarity')

    results = [{'name': node.name,
                'node_id': node.node_id,
                'path': ' > '.join([TaxonomyNode.objects.get(node_id=node_id).name for node_id in path_list]),
                'big_id': ','.join(path_list),
                'omitted': node.omitted_curation_task}
               for node in qs_results
               for path_list in taxonomy.get_hierarchy_paths(node.node_id)]

    return JsonResponse(results[:10], safe=False)


#############################
# CONTRIBUTE TO DATASET VIEWS
#############################

def contribute(request, short_name, beginner_task_finished=False):
    dataset = get_object_or_404(Dataset, short_name=short_name)

    n_contributors = User.objects.annotate(num_votes=Count('votes')).filter(num_votes__gt=0).count()

    user_is_maintainer = dataset.user_is_maintainer(request.user)

    # Get previously stored annotators ranking
    annotators_ranking = data_from_async_task(compute_annotators_ranking, [dataset.id], {},
                                              DATASET_ANNOTATORS_RANKING_TEMPLATE.format(dataset.id), 60 * 1)

    return render(request, 'datasets/contribute.html', {'dataset': dataset, 'n_contributors': n_contributors, 'annotators_ranking': annotators_ranking,
                                                        'beginner_task_finished': beginner_task_finished,
                                                        'user_is_maintainer': user_is_maintainer})


@login_required
def contribute_validate_annotations(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if request.GET.get('help', False):
        if request.session.get('read_instructions', False) or request.user.profile.contributed_two_weeks_ago:
            return render(request, 'datasets/contribute_validate_annotations_help.html', {'dataset': dataset, 'skip_tempo': True})
        else:
            return render(request, 'datasets/contribute_validate_annotations_help.html', {'dataset': dataset, 'skip_tempo': False})
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse('login') + '?next={0}'.format(
            reverse('contribute-validate-annotations', args=[dataset.short_name])))
    return render(request, 'datasets/contribute_validate_annotations.html', {'dataset': dataset})


@login_required
def contribute_validate_annotations_easy(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = request.GET.get('url_id')
    if not node_id:
        request.session['nb_task1_pages'] = 0
        nodes = TaxonomyNode.objects.filter(beginner_task=True).order_by('?')
        if nodes:
            for node in nodes:
                if dataset.user_can_annotate(node.node_id, request.user):
                    node_id = node.url_id
                    break
    if not node_id:
        return contribute(request, short_name, beginner_task_finished=True)
    return contribute_validate_annotations_category(request, short_name, node_id,
                                                    html_url='datasets/contribute_validate_annotations_category_easy.html')


@login_required
def contribute_validate_annotations_all(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    request.session['nb_task1_pages'] = 0
    new_annotations = request.GET.get('na', 0)  # new annotations (for Kaggle dataset)
    if user_is_maintainer:
        return render(request, 'datasets/dataset_taxonomy_choose_category_all.html',
                      {'dataset': dataset, 'new_annotations': new_annotations})
    else:
        return contribute(request, short_name)


def get_candidate_annotations_complete_ids_random_from(candidate_annotation_ids):
    """
        order them by number of ground truth annotations that the corresponding sound has, and
        randomize (for complete labeling
    """
    with connection.cursor() as cursor:
        if len(candidate_annotation_ids):
            cursor.execute("""
                  SELECT "datasets_candidateannotation"."id",
                  COUNT(
                  CASE "datasets_groundtruthannotation"."from_propagation" WHEN False then 1 ELSE NULL END) 
                  AS "num_sound_gt"
                  FROM "datasets_candidateannotation"
                  INNER JOIN "datasets_sounddataset"
                  ON ("datasets_candidateannotation"."sound_dataset_id" = "datasets_sounddataset"."id")
                  LEFT OUTER JOIN "datasets_groundtruthannotation"
                  ON ("datasets_sounddataset"."id" = "datasets_groundtruthannotation"."sound_dataset_id")
                  WHERE "datasets_candidateannotation"."id" IN %s
                  GROUP BY "datasets_candidateannotation"."id" ORDER BY "num_sound_gt"
                  DESC, RANDOM() limit 12;""", [tuple(candidate_annotation_ids)])
            return [i[0] for i in cursor.fetchall()]
        else:
            return []


PresentNotPresentUnsureFormSet = formset_factory(PresentNotPresentUnsureForm)


@login_required
def contribute_validate_annotations_category(request, short_name, node_id, html_url=None):
    NB_TOTAL_ANNOTATIONS = 12
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user = request.user
    user_is_maintainer = dataset.user_is_maintainer(user)
    user_last_category = user.profile.last_category_annotated
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    skip_tempo = True if user_last_category == node and user.profile.contributed_recently or \
                         request.GET.get(settings.SKIP_TEMPO_PARAMETER, False) else False
    maintainer_task = request.GET.get('mt', 0)
    new_annotations = request.GET.get('na', 0)  # new annotations (for Kaggle dataset)

    annotation_ids = []
    # check if user annotate a new category or has not annotate for a long time
    # make him fail the test and reset countdown
    if user_last_category != node or not user.profile.contributed_recently:
        user.profile.test = 'FA'
        user.profile.refresh_countdown()

    user_test = user.profile.test
    sound_examples_verification = node.freesound_examples_verification.all().filter(deleted_in_freesound=False)
    annotation_examples_verification_ids = dataset.candidate_annotations.filter(sound_dataset__sound__in=sound_examples_verification,
                                                                      taxonomy_node=node).values_list('id', flat=True)

    sound_examples = node.freesound_examples.all().filter(deleted_in_freesound=False)
    annotation_examples_ids = dataset.candidate_annotations.filter(sound_dataset__sound__in=sound_examples, taxonomy_node=node)\
        .values_list('id', flat=True)

    if node.positive_verification_examples_activated:
        # Check if user has passed the test to know if it is needed to add test examples to the form
        if user_test == 'FA':
            N_verification_examples = min(2, len(annotation_examples_verification_ids))
            annotation_ids += random.sample(list(annotation_examples_verification_ids), N_verification_examples)

    negative_annotation_example = False
    if node.negative_verification_examples_activated:
        # Get negative examples and add one if user has failed the test
        if user_test == 'FA':
            negative_sound_examples = node.freesound_false_examples.filter(deleted_in_freesound=False).order_by('?')
            if negative_sound_examples:
                negative_sound_example = negative_sound_examples[0]
                # create "dummy" annotation example for the false example of id 0 (the corresponding annotation does
                # not exist in the Annotation table because it is a false irrelevant example)
                negative_annotation_example = CandidateAnnotation(sound_dataset=SoundDataset(
                    sound=negative_sound_example, dataset=dataset), id=0)
                annotation_ids += [None]  # count as an added annotation but does not retrieve any annotation later,
                #  the false annotation "negative_annotation_example" is added manually

    # Get non ground truth annotations, never voted by the user (with positive test),
    # exclude test examples, order by priority score & random,
    # exclude candidate outside of [0.3, 30] sec and with 0 votes
    # TODO: put this in a class method and do a test
    annotations = dataset.non_ground_truth_annotations_per_taxonomy_node(node_id)\
                         .exclude(id__in=Vote.objects.filter(candidate_annotation__taxonomy_node=node,
                                                             created_by=user,
                                                             test__in=('UN', 'AP', 'PP', 'NA', 'NP'))
                                  .values('candidate_annotation_id'))\
                         .exclude(id__in=annotation_examples_verification_ids)\
                         .exclude(id__in=annotation_examples_ids)\
                         .filter(sound_dataset__sound__deleted_in_freesound=False)\
                         .order_by('-priority_score', '?')

    # Exclude annotations that have votes (for kaggle dataset) and that have nc and sampling+ licenses
    if new_annotations == '1':
        # this will discard the annotations with no votes
        # out of [0.3, 30] secondes
        # and with NC licenses
        annotations = annotations\
            .exclude(priority_score__gte=1000)\
            .exclude(priority_score__lte=100)\
            .exclude(sound_dataset__sound__extra_data__license__in=('http://creativecommons.org/licenses/by-nc/3.0/',
                                                                    'http://creativecommons.org/licenses/sampling+/1.0/'
                                                                    ))

    N_ANNOTATIONS_TO_VALIDATE = NB_TOTAL_ANNOTATIONS - len(annotation_ids)
    annotation_ids += annotations[:N_ANNOTATIONS_TO_VALIDATE].values_list('id', flat=True)

    # If not candidate annotations left, remove test annotations
    if annotations.count() == 0:
        annotation_ids = list()
        negative_annotation_example = list()

    # Get the selected annotations
    N = len(annotation_ids)
    annotations_to_validate = list(CandidateAnnotation.objects.filter(id__in=annotation_ids)
                                   .select_related('sound_dataset__sound'))
    if negative_annotation_example:  # add the "dummy" negative example annotation if it exists
        annotations_to_validate.append(negative_annotation_example)
    random.shuffle(annotations_to_validate)

    formset = PresentNotPresentUnsureFormSet(
        initial=[{'annotation_id': annotation.id} for annotation in annotations_to_validate])
    annotations_forms = list(zip(list(annotations_to_validate), formset))

    category_comment_form = CategoryCommentForm()

    nb_task1_pages = request.session.get('nb_task1_pages', False)
    if not nb_task1_pages or nb_task1_pages > 6 or user_last_category != node:
        request.session['nb_task1_pages'] = 1
        nb_task1_pages = 1

    # For beginner task html_url argument is given
    if not html_url:
        html_url = 'datasets/contribute_validate_annotations_category.html'

    return render(request, html_url,
                  {'dataset': dataset, 'node': node, 'annotations_forms': annotations_forms,
                   'formset': formset, 'N': N, 'user_is_maintainer': user_is_maintainer,
                   'category_comment_form': category_comment_form, 'skip_tempo': skip_tempo,
                   'skip_tempo_parameter': settings.SKIP_TEMPO_PARAMETER,
                   'nb_task1_pages': nb_task1_pages,
                   'maintainer_task': maintainer_task,
                   'new_annotations': new_annotations})


@login_required
@transaction.atomic
def save_contribute_validate_annotations_category(request):
    if request.method == 'POST':
        comment_form = CategoryCommentForm(request.POST)
        formset = PresentNotPresentUnsureFormSet(request.POST)
        if formset.is_valid() and comment_form.is_valid():
            update_test_state = False
            from_test_page = False
            test_annotations_id = []
            annotations_id = [form.cleaned_data['annotation_id'] for form in formset if 'vote' in form.cleaned_data]
            # filter out the annotation id = 0 corresponding to dummy annotations for false example
            one_real_annotation_id = [annotation_id for annotation_id in annotations_id if annotation_id != 0][0]
            node_id = CandidateAnnotation.objects.get(id=one_real_annotation_id).taxonomy_node.node_id
            node = TaxonomyNode.objects.get(node_id=node_id)
            # extract test examples if the user test is fail
            if request.user.profile.test == 'FA':
                from_test_page = True
                # positive examples
                positive_test = None  # count as deactivated
                if node.positive_verification_examples_activated:
                    test_annotations_id = CandidateAnnotation.objects.filter(taxonomy_node=node,
                                                                    sound_dataset__sound__in=node.freesound_examples_verification.all())\
                        .values_list('id', flat=True)
                    vote_test_annotations = [form.cleaned_data['vote'] for form in formset
                                             if 'vote' in form.cleaned_data
                                             if form.cleaned_data['annotation_id'] in test_annotations_id]
                    if len(vote_test_annotations) > 0:  # if there is not test annotation, test is considered deactivated
                        positive_test = all(v in ('0.5', '1') for v in vote_test_annotations)

                # false examples
                negative_test = None  # count as deactivated
                if node.negative_verification_examples_activated:
                    vote_false_test_annotations = [form.cleaned_data['vote'] for form in formset
                                                   if 'vote' in form.cleaned_data
                                                   if form.cleaned_data['annotation_id'] == 0]  # take false example form
                    if len(vote_false_test_annotations) > 0:  # if there is not test annotation, test test is considered deactivated
                        negative_test = all(v == '-1' for v in vote_false_test_annotations)

                # check answers and update user test field
                if positive_test is True and negative_test is True:  # both test activated, both succeed
                    request.user.profile.test = 'AP'
                elif positive_test is True and negative_test is None:  # positive test activated and succeed
                    request.user.profile.test = 'PP'
                elif positive_test is None and negative_test is True:  # negative test activated and succeed
                    request.user.profile.test = 'NP'
                elif positive_test is None and negative_test is None:  # both tests deactivated or no test examples available for the category
                    request.user.profile.test = 'NA'
                elif positive_test is False or negative_test is False:  # one of the test failed
                    request.user.profile.test = 'FA'
                request.user.profile.refresh_countdown()
                request.user.profile.countdown_trustable -= 1

            else:  # user passed the test: check the countdown and decrement it if needed
                if request.user.profile.countdown_trustable < 2:  # change user test to failed after storing votes
                    update_test_state = True
                else:  # decrement to the countdown
                    request.user.profile.countdown_trustable -= 1
            request.user.profile.last_category_annotated = node
            request.user.save()

            # get from which task (beginner or advanced) the user submitted his votes
            from_task = request.POST.get('from_task')

            for form in formset:
                if 'vote' in form.cleaned_data:  # This is to skip last element of formset which is empty
                    annotation_id = form.cleaned_data['annotation_id']
                    if annotation_id not in test_annotations_id and annotation_id != 0:  # store only the votes for non test annotations
                        check = Vote.objects.filter(created_by=request.user,
                                                    candidate_annotation_id=annotation_id,
                                                    created_at__gt=timezone.now()
                                                                   - datetime.timedelta(seconds=5))
                        if not check.exists():
                            # Save votes for annotations
                            Vote.objects.create(
                                created_by=request.user,
                                vote=float(form.cleaned_data['vote']),
                                visited_sound=form.cleaned_data['visited_sound'],
                                candidate_annotation_id=annotation_id,
                                test=request.user.profile.test,
                                from_test_page=from_test_page,
                                from_task=from_task,
                            )

            if comment_form.cleaned_data['comment'].strip():  # If there is a comment
                comment = comment_form.save(commit=False)
                comment.created_by = request.user
                comment.save()

            if request.session.get('nb_task1_pages', False):
                request.session['nb_task1_pages'] += 1

            if update_test_state:
                request.user.profile.test = 'FA'
                request.user.save()
        else:
            error_response = {'errors': [count for count, value in enumerate(formset.errors) if value != {}]}
            return JsonResponse(error_response)
    return JsonResponse({'errors': False})


@login_required
def choose_category(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    request.session['read_instructions'] = True
    request.session['nb_task1_pages'] = 0
    return render(request, 'datasets/dataset_taxonomy_choose_category.html', {'dataset': dataset})


@login_required
def choose_category_all(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    request.session['read_instructions'] = True
    request.session['nb_task1_pages'] = 0
    return render(request, 'datasets/dataset_taxonomy_choose_category_all.html', {'dataset': dataset})


def dataset_taxonomy_table_choose(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    taxonomy = dataset.taxonomy
    hierarchy_paths = []
    end_of_table = False
    add_label_or_choose_category = request.POST.get('add_label_or_choose_category', 'choose_category')

    # nodes for Free choose table
    if request.method == 'POST':
        node_id = request.POST['node_id']

        # choose a category at the given node_id level
        if node_id != str(0):
            if node_id in [node.node_id for node in taxonomy.get_nodes_at_level(0)]:
                # remove node that them and all their children are omitted.
                # Here we should remove also the categories which all its children have no more annotations tu validate.
                # Doing it with dataset.get_categories_to_validate() or with dataset.user_can_annotated() on all
                # children would be too slow
                if add_label_or_choose_category == 'choose_category':
                    nodes = [node for node in taxonomy.get_children(node_id) if node.self_and_children_advanced_task
                             and not node.self_and_children_omitted]
                else:
                    nodes = [node for node in taxonomy.get_children(node_id)]
            else:
                end_of_table = True  # end of continue, now the user will choose a category to annotate
                nodes = list(taxonomy.get_all_children(node_id)) + [taxonomy.get_element_at_id(node_id)] \
                    + list(taxonomy.get_all_parents(node_id))
                # we should remove the nodes that have no more annotations to validate for the user
                # by using dataset.user_can_annotate(), but it is too slow
                if add_label_or_choose_category == 'choose_category':
                    nodes = [node for node in nodes
                             if node.advanced_task and not node.omitted]
                else:
                    pass
            hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node_id)

        # start choosing category
        else:
            nodes = taxonomy.get_nodes_at_level(0)
            nodes = [node for node in nodes if node.self_and_children_advanced_task
                     and not node.self_and_children_omitted]
        nodes = sorted(nodes, key=lambda n: n.nb_ground_truth)

    # GET request, nodes for Our priority table
    else:
        end_of_table = True
        nodes = dataset.get_categories_to_validate(request.user).filter(advanced_task=True)\
            .exclude(omitted=True).order_by('nb_ground_truth')[:20]

    return render(request, 'datasets/dataset_taxonomy_table_choose.html', {
        'dataset': dataset, 'end_of_table': end_of_table, 'hierarchy_paths': hierarchy_paths, 'nodes': nodes,
        'add_label_or_choose_category': add_label_or_choose_category})


def dataset_taxonomy_table_search(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    nodes = dataset.get_categories().filter(advanced_task=True)  # sould use get_categories_to_validate() but it is too slow
    return render(request, 'datasets/dataset_taxonomy_table_search.html',
                  {'dataset': dataset, 'nodes': nodes, 'maintainer_task': 0, 'new_annotations': 0})


def dataset_taxonomy_table_search_all(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    new_annotations = request.GET.get('na', 0)  # new annotations (for Kaggle dataset)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    nodes = dataset.get_categories().exclude(omitted=True)  # sould use get_categories_to_validate() but it is too slow
    return render(request, 'datasets/dataset_taxonomy_table_search.html',
                  {'dataset': dataset, 'nodes': nodes,
                   'maintainer_task': 1,
                   'new_annotations': new_annotations})


def get_mini_node_info(request, short_name, node_id):
    show_examples = int(request.GET.get('se', 1))
    show_go_button = int(request.GET.get('sb', 1))
    show_num_gt = int(request.GET.get('sgt', 0))
    show_hierarchy = int(request.GET.get('sh', 1))
    show_name_table_lines = int(request.GET.get('sn', 1))
    node_id = unquote(node_id)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node = dataset.taxonomy.get_element_at_id(node_id).as_dict()
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node['node_id'])
    node['hierarchy_paths'] = hierarchy_paths if hierarchy_paths is not None else []
    return render(request, 'datasets/taxonomy_node_mini_info.html',
                  {'dataset': dataset, 'node': node, 'show_examples': show_examples,
                   'show_go_button': show_go_button, 'show_num_gt': show_num_gt,
                   'show_hierarchy': show_hierarchy, 'show_name_table_lines': show_name_table_lines})


@login_required
def curate_sounds(request, short_name, sound_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed
    taxonomy = dataset.taxonomy
    sound = get_object_or_404(Sound, freesound_id=sound_id)
    existing_gt_annotations = sound.get_ground_truth_annotations(dataset)\
                                .filter(from_propagation=False, taxonomy_node__omitted_curation_task=False)\
                                .select_related('taxonomy_node')
    existing_candidate_annotations = sound.get_candidate_annotations(dataset)\
                                          .filter(ground_truth=None, taxonomy_node__omitted_curation_task=False)\
                                          .select_related('taxonomy_node')\
                                          .exclude(taxonomy_node__id__in=
                                                existing_gt_annotations.values_list('taxonomy_node__id', flat=True))
    existing_gt_annotations_formated = [
        {
            'node_id': annotation.taxonomy_node.node_id,
            'node_name': annotation.taxonomy_node.name,
            'ground_truth': annotation.ground_truth,
            'big_id': ','.join(taxonomy.get_hierarchy_paths(annotation.taxonomy_node.node_id)[0]),
        } for annotation in existing_gt_annotations]
    
    existing_candidate_annotations_formated = [
        {
            'node_id': annotation.taxonomy_node.node_id,
            'node_name': annotation.taxonomy_node.name,
            'big_id': ','.join(taxonomy.get_hierarchy_paths(annotation.taxonomy_node.node_id)[0]),
        } for annotation in existing_candidate_annotations]
    
    freesound_sound_id = sound.freesound_id
    return render(request, 'datasets/curate_sounds.html',
                  {'dataset': dataset,
                   'freesound_sound_id': freesound_sound_id,
                   'generation_task': '1',
                   'existing_gt_annotations': existing_gt_annotations_formated,
                   'existing_candidate_annotations': existing_candidate_annotations_formated})


@transaction.atomic
def save_expert_votes_curation_task(request, short_name, sound_id):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed
    if request.method == 'POST':
        annotation_votes = json.loads(request.POST.dict()['jsonData'])
        # check that all the annotations are voted
        if not all('label-presence' in annotation_vote for annotation_vote in annotation_votes):
            error_response = {'errors': [value['label-id'] for count, value in enumerate(annotation_votes) if 'label-presence' not in value]}
            return JsonResponse(error_response)
        else:
            # create candidate annotations and expert votes
            # we can treat both case at once thanks to get_or_create() method
            for new_annotation_vote in annotation_votes:
                annotation, _ = CandidateAnnotation.objects.get_or_create(
                    sound_dataset=SoundDataset.objects.get(sound__freesound_id=sound_id, 
                                                           dataset=dataset),
                    taxonomy_node=TaxonomyNode.objects.get(node_id=new_annotation_vote['label-id']),
                    defaults={
                        'type': 'MA',
                        'created_by': request.user,
                    }
                )
                Vote.objects.create(
                    created_by=request.user,
                    vote=new_annotation_vote['label-presence'],
                    candidate_annotation=annotation,
                    from_task='CU',
                    from_expert=True,
                )

    return JsonResponse({'errors': False})


def get_node_info(request, short_name, node_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    generation_task = request.GET.get('gen-task', '0')
    node = dataset.taxonomy.get_element_from_name(node_name)
    hp = [node.get_parents()]
    node = node.as_dict()
    return render(request, 'datasets/taxonomy_node_info_for_taxonomy_table.html',
                  {
                      'dataset': dataset,
                      'node': node,
                      'hp': hp,
                      'generation_task': generation_task,
                  })


########################
# DOWNLOAD DATASET VIEWS
########################
def downloads(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'datasets/downloads.html', {'dataset': dataset})


def get_access_token(request):
    code = request.GET.get('code', None)
    refresh_token = request.GET.get('refresh_token', None)
    if not code and not refresh_token:
        return HttpResponseBadRequest()

    data = {
            'client_id': settings.FS_CLIENT_ID,
            'client_secret': settings.FS_CLIENT_SECRET,
    }
    if code:
        data['code'] = code
        data['grant_type'] = 'authorization_code'
    else:
        data['refresh_token'] = refresh_token
        data['grant_type'] = 'refresh_token'

    access_token_url = "https://www.freesound.org/apiv2/oauth2/access_token/"
    data = urlencode(data).encode('ascii')

    try:
        with urlopen(access_token_url, data) as response:
            response = response.read().decode()
        return HttpResponse(response)
    except HTTPError:
        return HttpResponseBadRequest()


@cache_page(60 * 60 * 24)
def dataset_sounds(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return JsonResponse({'sounds': [s.id for s in dataset.sounds.all()]})


@login_required
@user_passes_test(lambda u: u.is_staff)  # Restrict download to admins (this is a temporal thing)
def download_script(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="fs_download_script.py"'
    script = utils.generate_download_script(dataset)
    response.write(script)
    return response


def release_explore(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, release_tag=release_tag)
    user_is_maintainer = dataset.user_is_maintainer(request.user)

    return render(request, 'datasets/release_explore.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'release': release
    })


@login_required
def download_release(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, dataset=dataset, release_tag=release_tag)
    if release.type is not 'PU' and not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    script = utils.generate_download_script(dataset)
    formatted_script = highlight(script, PythonLexer(), HtmlFormatter())
    highlighting_styles = HtmlFormatter().get_style_defs('.highlight')
    return render(request, 'datasets/download.html', {'dataset': dataset,
                                             'release': release,
                                             'formatted_script': formatted_script,
                                             'highlighting_styles': highlighting_styles})


@login_required
def change_release_type(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, dataset=dataset, release_tag=release_tag)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    release_type = request.GET.get('release-type', None)
    if release_type not in [item[0] for item in DatasetRelease.TYPE_CHOICES]:
        release_type = DatasetRelease.TYPE_CHOICES[0][0]
    release.type = release_type
    release.save()

    return HttpResponseRedirect(reverse('dataset-explore', args=[dataset.short_name]))


@login_required
def delete_release(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    # Remove related files and db object
    for release in DatasetRelease.objects.filter(dataset=dataset, release_tag=release_tag):
        try:
            os.remove(release.index_file_path)
        except FileNotFoundError:
            pass
        release.delete()

    return HttpResponseRedirect(reverse('dataset-explore', args=[dataset.short_name]))


@login_required
def check_release_progresses(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    return JsonResponse({release.id: release.processing_progress for release in dataset.releases})


def dataset_release_table(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, release_tag=release_tag)
    user_is_maintainer = dataset.user_is_maintainer(request.user)

    return render(request, 'datasets/dataset_release_table.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'release': release
    })
