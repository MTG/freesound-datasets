from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.db import transaction
from django.forms import formset_factory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datasets.models import Dataset, DatasetRelease, Annotation, Vote, TaxonomyNode
from datasets import utils
from datasets.forms import DatasetReleaseForm, PresentNotPresentUnsureForm, CategoryCommentForm
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from datasets.tasks import generate_release_index, compute_dataset_basic_stats, compute_dataset_taxonomy_stats, \
    compute_annotators_ranking
from utils.redis_store import store, DATASET_BASIC_STATS_KEY_TEMPLATE, DATASET_TAXONOMY_STATS_KEY_TEMPLATE, \
    DATASET_ANNOTATORS_RANKING_TEMPLATE
from utils.async_tasks import data_from_async_task
import os
import random
import json


#######################
# EXPLORE DATASET VIEWS
#######################

def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    form_errors = False
    if request.method == 'POST':
        form = DatasetReleaseForm(request.POST)
        if form.is_valid():
            dataset_release = form.save(commit=False)
            dataset_release.dataset = dataset
            dataset_release.save()
            async_job = generate_release_index.delay(dataset.id, dataset_release.id, form.cleaned_data['max_number_of_sounds'])
            form = DatasetReleaseForm()  # Reset form
        else:
            form_errors = True
    else:
        form = DatasetReleaseForm()
        
    return render(request, 'datasets/dataset.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'dataset_release_form': form, 'dataset_release_form_errors': form_errors,
    })


def dataset_taxonomy_tree(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
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

    return render(request, 'datasets/dataset_releases_table.html', {
        'dataset': dataset,
        'dataset_basic_stats': dataset_basic_stats,
        'user_is_maintainer': user_is_maintainer,
        'dataset_releases_for_user': dataset_releases_for_user
    })


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    sound_list = dataset.sounds_per_taxonomy_node(node_id)
    paginator = Paginator(sound_list, 10)
    page = request.GET.get('page')
    try:
        sounds = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        sounds = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        sounds = paginator.page(paginator.num_pages)
        
    return render(request, 'datasets/taxonomy_node.html', {'dataset': dataset, 'node': node, 'sounds': sounds,
                                                           'user_is_maintainer': user_is_maintainer})

#############################
# CONTRIBUTE TO DATASET VIEWS
#############################

def contribute(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)

    # Get previously stored annotators ranking
    annotators_ranking = data_from_async_task(compute_annotators_ranking, [dataset.id], {},
                                              DATASET_ANNOTATORS_RANKING_TEMPLATE.format(dataset.id), 60 * 1)

    return render(request, 'datasets/contribute.html', {'dataset': dataset, 'annotators_ranking': annotators_ranking})

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


PresentNotPresentUnsureFormSet = formset_factory(PresentNotPresentUnsureForm)

@login_required
def contribute_validate_annotations_category(request, short_name, node_id):
    NB_TOTAL_ANNOTATIONS = 12
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user = request.user
    user_is_maintainer = dataset.user_is_maintainer(user)
    user_last_category = user.profile.last_category_annotated
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    skip_tempo = True if user_last_category == node and user.profile.contributed_recently or \
                         request.GET.get(settings.SKIP_TEMPO_PARAMETER, False) else False

    annotation_ids = []
    # check if user annotate a new category or has not annotate for a long time
    # make him fail the test and reset countdown
    if user_last_category != node or not user.profile.contributed_recently:
        user.profile.test = 'FA'
        user.profile.refresh_countdown()

    user_test = user.profile.test
    sound_examples = node.freesound_examples.all()
    annotation_examples = dataset.annotations.filter(sound_dataset__sound__in=sound_examples, taxonomy_node=node,
                                                     sound_dataset__sound__deleted_in_freesound=False)

    if node.positive_verification_examples_activated:
        # Check if user has passed the test to know if it is needed to add test examples to the form
        if user_test == 'FA':
            annotation_ids += annotation_examples.values_list('id', flat=True)[:2]  # add 2 test examples TODO:select random

    if node.negative_verification_examples_activated:
        # Get negative examples and add one if user has failed the test
        if user_test == 'FA':
            negative_sound_examples = node.freesound_false_examples.all()
            negative_annotation_examples = dataset.annotations.filter(sound_dataset__sound__in=negative_sound_examples,
                                                                      taxonomy_node=node,
                                                                      sound_dataset__sound__deleted_in_freesound=False)
            if negative_annotation_examples:
                annotation_ids += random.sample(negative_annotation_examples.values_list('id', flat=True), 1)

    # Get annotation that are not ground truth and that have been never annotated by the user, exclude test examples
    annotations = dataset.non_ground_truth_annotations_per_taxonomy_node(node_id) \
        .exclude(votes__created_by=user).exclude(id__in=annotation_examples.values_list('id', flat=True)) \
        .filter(sound_dataset__sound__deleted_in_freesound=False).annotate(num_votes=Count('votes'))

    # Extract the voted annotations ids
    annotation_with_vote_ids = annotations.filter(num_votes__gt=0).values_list('id', flat=True)

    # Select 12 (- num of test examples) annotations prioritizing annotations that have been already voted, randomize
    # TODO: Maybe use weighted sampling to avoid this 2 step selection (may include more steps in the future...)
    N_ANNOTATIONS_TO_VALIDATE = NB_TOTAL_ANNOTATIONS - len(annotation_ids)
    N_with_vote = min(len(annotation_with_vote_ids), N_ANNOTATIONS_TO_VALIDATE)
    if N_with_vote:
        annotation_ids += random.sample(list(annotation_with_vote_ids), N_with_vote)

    # if there is not enough voted annotations (<12), add non voted annotations corresponding to short clips
    if len(annotation_ids) < NB_TOTAL_ANNOTATIONS:
        annotation_with_no_vote_short_ids = annotations.filter(num_votes=0,
                                                               sound_dataset__sound__extra_data__duration__lte=10)\
            .values_list('id', flat=True)
        N_with_no_vote_short = min(len(annotation_with_no_vote_short_ids), N_ANNOTATIONS_TO_VALIDATE - N_with_vote)
        if N_with_no_vote_short:
            annotation_ids += random.sample(list(annotation_with_no_vote_short_ids), N_with_no_vote_short)

        # if there is not enough (<12), fill the list with non voted annotations
        if len(annotation_ids) < NB_TOTAL_ANNOTATIONS:
            annotation_with_no_vote_ids = annotations.filter(num_votes=0)\
                .exclude(id__in=annotation_with_no_vote_short_ids)\
                .values_list('id', flat=True)
            N_with_no_vote = min(len(annotation_with_no_vote_ids), N_ANNOTATIONS_TO_VALIDATE - N_with_vote - N_with_no_vote_short)
            if N_with_no_vote:
                annotation_ids += random.sample(list(annotation_with_no_vote_ids), N_with_no_vote)

    N = len(annotation_ids)
    annotations = Annotation.objects.filter(id__in=annotation_ids).select_related('sound_dataset__sound')

    formset = PresentNotPresentUnsureFormSet(
        initial=[{'annotation_id': annotation.id} for annotation in annotations])
    annotations_forms = list(zip(list(annotations), formset))

    category_comment_form = CategoryCommentForm()

    return render(request, 'datasets/contribute_validate_annotations_category.html',
                  {'dataset': dataset, 'node': node, 'annotations_forms': annotations_forms,
                   'formset': formset, 'N': N, 'user_is_maintainer': user_is_maintainer,
                   'category_comment_form': category_comment_form, 'skip_tempo': skip_tempo,
                   'skip_tempo_parameter': settings.SKIP_TEMPO_PARAMETER})


@login_required
@transaction.atomic
def save_contribute_validate_annotations_category(request):
    if request.method == 'POST':
        comment_form = CategoryCommentForm(request.POST)
        formset = PresentNotPresentUnsureFormSet(request.POST)
        if formset.is_valid() and comment_form.is_valid():
            test_annotations_id = []
            annotations_id = [form.cleaned_data['annotation_id'] for form in formset if 'vote' in form.cleaned_data]
            # extract test examples if the user test is fail
            if request.user.profile.test == 'FA':
                node = TaxonomyNode.objects.get(node_id=Annotation.objects.get(id=annotations_id[0]).
                                                taxonomy_node.node_id)
                # positive examples
                positive_test = None  # count as deactivated
                if node.positive_verification_examples_activated:
                    test_annotations_id = Annotation.objects.filter(taxonomy_node=node,
                                                                    sound_dataset__sound__in=node.freesound_examples.all())\
                        .values_list('id', flat=True)
                    vote_test_annotations = [form.cleaned_data['vote'] for form in formset
                                             if 'vote' in form.cleaned_data
                                             if form.cleaned_data['annotation_id'] in test_annotations_id]
                    if len(vote_test_annotations) > 0:  # if there is not test annotation, test is considered deactivated
                        positive_test = all(v == '1' for v in vote_test_annotations)

                # false examples
                negative_test = None  # count as deactivated
                if node.negative_verification_examples_activated:
                    false_test_annotations_id = Annotation.objects.filter(taxonomy_node=node,
                                                                          sound_dataset__sound__in=node.freesound_false_examples.all())\
                        .values_list('id', flat=True)
                    vote_false_test_annotations = [form.cleaned_data['vote'] for form in formset
                                                   if 'vote' in form.cleaned_data
                                                   if form.cleaned_data['annotation_id'] in false_test_annotations_id]
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

            else:  # user passed the test: check the countdown and decrement it if needed
                if request.user.profile.countdown_trustable < 2:  # user test is now in failed state
                    request.user.profile.test = 'FA'
                else:  # decrement to the countdown
                    request.user.profile.countdown_trustable -= 1
            request.user.profile.last_category_annotated = TaxonomyNode.objects.get(
                node_id=Annotation.objects.get(id=annotations_id[0]).taxonomy_node.node_id)
            request.user.save()

            for form in formset:
                if 'vote' in form.cleaned_data:  # This is to skip last element of formset which is empty
                    annotation_id = form.cleaned_data['annotation_id']
                    if annotation_id not in test_annotations_id:  # store only the votes for non test annotations
                        check = Vote.objects.filter(created_by=request.user,
                                                    annotation_id=annotation_id)
                        if not check.exists():
                            # Save votes for annotations
                            Vote.objects.create(
                                created_by=request.user,
                                vote=float(form.cleaned_data['vote']),
                                visited_sound=form.cleaned_data['visited_sound'],
                                annotation_id=annotation_id,
                                test=request.user.profile.test,
                            )

            if comment_form.cleaned_data['comment'].strip():  # If there is a comment
                comment = comment_form.save(commit=False)
                comment.created_by = request.user
                comment.save()
        else:
            error_response = {'errors': [count for count, value in enumerate(formset.errors) if value != {}]}
            return JsonResponse(error_response)
    return JsonResponse({'errors': False})


@login_required
def choose_category(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    request.session['read_instructions'] = True
    return render(request, 'datasets/dataset_taxonomy_choose_category.html', {'dataset': dataset})


def dataset_taxonomy_table_choose(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    taxonomy = dataset.taxonomy
    hierarchy_paths = []
    end_of_table = False

    # nodes for Free choose table
    if request.method == 'POST':
        node_id = request.POST['node_id']

        # choose a category at the given node_id level
        if node_id != str(0):
            if node_id in taxonomy.get_nodes_at_level(0).values_list('node_id', flat=True):
                # remove node that them and all their children are omitted
                nodes = [node for node in taxonomy.get_children(node_id) if not node.self_and_children_omitted]
            else:
                end_of_table = True  # end of continue, now the user will choose a category to annotate
                nodes = taxonomy.get_all_children(node_id) + [taxonomy.get_element_at_id(node_id)] + taxonomy.get_all_parents(node_id)
                # remove the nodes that have no more annotations to validate for the user, or are omitted
                nodes = [node for node in nodes
                         if dataset.user_can_annotate(node.node_id, request.user) and not node.omitted]
            hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node_id)

        # start choosing category
        else:
            nodes = taxonomy.get_nodes_at_level(0)
        nodes = sorted(nodes, key=lambda n: n.nb_ground_truth)

    # GET request, nodes for Our priority table
    else:
        end_of_table = True
        nodes = dataset.get_categories_to_validate(request.user).exclude(omitted=True).order_by('nb_ground_truth')

    return render(request, 'datasets/dataset_taxonomy_table_choose.html', {
        'dataset': dataset, 'end_of_table': end_of_table, 'hierarchy_paths': hierarchy_paths, 'nodes': nodes})


def dataset_taxonomy_table_search(request, short_name):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    taxonomy = dataset.taxonomy
    nodes = dataset.get_categories_to_validate(request.user).exclude(omitted=True)
    return render(request, 'datasets/dataset_taxonomy_table_search.html', {'dataset': dataset, 'nodes': nodes})


def get_mini_node_info(request, short_name, node_id):
    node_id = unquote(node_id)
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node = dataset.taxonomy.get_element_at_id(node_id).as_dict()
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node['node_id'])
    node['hierarchy_paths'] = hierarchy_paths if hierarchy_paths is not None else []
    return render(request, 'datasets/taxonomy_node_mini_info.html', {'dataset': dataset, 'node': node})


########################
# DOWNLOAD DATASET VIEWS
########################

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

    return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))


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

    return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))


@login_required
def check_release_progresses(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    return JsonResponse({release.id: release.processing_progress for release in dataset.releases})
