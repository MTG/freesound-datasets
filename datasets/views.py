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
from django.forms import formset_factory
from datasets.models import Dataset, DatasetRelease, Annotation, Vote
from datasets import utils
from datasets.forms import DatasetReleaseForm, PresentNotPresentUnsureForm
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

    return render(request, 'dataset.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'dataset_release_form': form, 'dataset_release_form_errors': form_errors,
    })


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

    return render(request, 'dataset_taxonomy_table.html', {
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

    return render(request, 'dataset_releases_table.html', {
        'dataset': dataset,
        'dataset_basic_stats': dataset_basic_stats,
        'user_is_maintainer': user_is_maintainer,
        'dataset_releases_for_user': dataset_releases_for_user
    })


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'taxonomy_node.html', {'dataset': dataset, 'node': node})


#############################
# CONTRIBUTE TO DATASET VIEWS
#############################

@login_required
def contribute(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)

    # Get previously stored annotators ranking
    annotators_ranking = data_from_async_task(compute_annotators_ranking, [dataset.id, request.user.id], {},
                                              DATASET_ANNOTATORS_RANKING_TEMPLATE.format(dataset.id), 60 * 1)

    return render(request, 'contribute.html', {'dataset': dataset, 'annotators_ranking': annotators_ranking})


@login_required
def contribute_validate_annotations(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'contribute_validate_annotations.html', {'dataset': dataset})


PresentNotPresentUnsureFormSet = formset_factory(PresentNotPresentUnsureForm)

@login_required
def contribute_validate_annotations_category(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)

    # Get non-validated annotations for this category
    annotations = dataset.annotations_per_taxonomy_node(node_id).annotate(num_votes=Count('votes')).filter(num_votes__lte=0)
    all_annotation_object_ids = annotations.values_list('id', flat=True)

    # Select 10 at random and return their Annotation objects
    N_ANNOTATIONS_TO_VALIDATE = 10
    N = min(len(all_annotation_object_ids), N_ANNOTATIONS_TO_VALIDATE)
    annotations = Annotation.objects\
        .filter(id__in=random.sample(list(all_annotation_object_ids), N))\
        .select_related('sound_dataset__sound')

    formset = PresentNotPresentUnsureFormSet(
        initial=[{'annotation_id': annotation.id} for annotation in annotations])
    annotations_forms = zip(list(annotations), formset)

    return render(request, 'contribute_validate_annotations_category.html',
                  {'dataset': dataset, 'node': node, 'annotations_forms': annotations_forms,
                   'formset': formset, 'N': N})


@login_required
def save_contribute_validate_annotations_category(request):
    if request.method == 'POST':
        formset = PresentNotPresentUnsureFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                if 'vote' in form.cleaned_data:  # This is to skip last element of formset which is empty
                    # Save votes for annotations
                    Vote.objects.create(
                        created_by=request.user,
                        vote=int(form.cleaned_data['vote']),
                        annotation_id=form.cleaned_data['annotation_id'],
                    )
        else:
            error_response = {'errors': [count for count, value in enumerate(formset.errors) if value != {}]}
            return JsonResponse(error_response)
    return JsonResponse({'errors': False})


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
    return render(request, 'download.html', {'dataset': dataset,
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
