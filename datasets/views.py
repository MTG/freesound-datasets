from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.core.urlresolvers import reverse
from datasets.models import Dataset, DatasetRelease
from datasets import utils
from datasets.forms import DatasetReleaseForm
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from datasets.tasks import generate_release_index, compute_dataset_basic_stats, compute_dataset_taxonomy_stats
from utils.redis_store import store, DATASET_BASIC_STATS_KEY_TEMPLATE, DATASET_TAXONOMY_STATS_KEY_TEMPLATE
import os



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
        'e': ('explore-taxonomy-node', 'Explore'),
        'cva': ('contribute-validate-annotations-category', 'Choose this'),
    }[request.GET.get('link_to', 'e')]

    # Get previously stored dataset taxonomy stats
    dataset_taxonomy_stats, elapsed_time = \
        store.get(DATASET_TAXONOMY_STATS_KEY_TEMPLATE.format(dataset.id), include_elapsed_time=True)
    if elapsed_time > 60*5:
        # If redis data is older than 60 seconds, trigger recompute it (for next time)
        compute_dataset_taxonomy_stats.delay(dataset.id)

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
    dataset_basic_stats, elapsed_time = \
        store.get(DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), include_elapsed_time=True)
    if elapsed_time > 60*5:
        # If redis data is older than 60 seconds, trigger recompute it (for next time)
        compute_dataset_basic_stats.delay(dataset.id)

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
    return render(request, 'contribute.html', {'dataset': dataset})

@login_required
def contribute_validate_annotations(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'contribute_validate_annotations.html', {'dataset': dataset})

@login_required
def contribute_validate_annotations_category(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'taxonomy_node.html', {'dataset': dataset, 'node': node})


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
