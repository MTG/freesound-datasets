from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout as auth_logout
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from urllib.parse import quote
from datasets.models import Dataset
from datasets.tasks import compute_dataset_basic_stats
from utils.redis_store import DATASET_BASIC_STATS_KEY_TEMPLATE
from utils.async_tasks import data_from_async_task


@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/')
def crash_me(request):
    raise Exception('Everything is under control')


def index(request):
    try:
        dataset = Dataset.objects.get(short_name='fsd')
        release = dataset.datasetrelease_set.first()
        dataset_basic_stats = data_from_async_task(compute_dataset_basic_stats, [dataset.id], {},
                                                   DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), 60)
        num_categories_reached_goal = dataset_basic_stats.get('num_categories_reached_goal', None)
        num_non_omitted_nodes = dataset_basic_stats.get('num_non_omitted_nodes', None)
    except:
        num_categories_reached_goal = None
        num_non_omitted_nodes = None
        release = None
    datasets = Dataset.objects.all().order_by('created_at')
    
    return render(request, 'index.html', {'home': True,
                                          'num_categories_reached_goal': num_categories_reached_goal,
                                          'num_non_omitted_nodes': num_non_omitted_nodes,
                                          'release': release,
                                          'datasets': datasets})


def faq(request):
    return render(request, 'faq.html', {})


def discussion(request, short_name=None):
    if short_name:
        dataset = get_object_or_404(Dataset, short_name=short_name)
    else:
        dataset = None
    return render(request, 'discussion.html', {'dataset': dataset})


def login(request):
    next_url = quote(request.GET.get('next', ''))
    show_freesound = bool(settings.SOCIAL_AUTH_FREESOUND_KEY)

    tvars = {'next': next_url,
             'show_freesound': show_freesound,
             }
    return render(request, 'login.html', tvars)


def logout(request):
    auth_logout(request)
    return redirect('/')
