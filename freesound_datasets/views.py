from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from datasets.models import Dataset
from datasets.tasks import compute_dataset_basic_stats
from utils.redis_store import DATASET_BASIC_STATS_KEY_TEMPLATE
from utils.async_tasks import data_from_async_task
from social_core.pipeline.partial import partial
from django.template.context_processors import csrf


@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/')
def crash_me(request):
    raise Exception('Everything is under control')


def index(request):
    dataset = Dataset.objects.get(short_name='fsd')
    dataset_basic_stats = data_from_async_task(compute_dataset_basic_stats, [dataset.id], {},
                                               DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), 60)
    num_categories_reached_goal = dataset_basic_stats.get('num_categories_reached_goal', None)
    num_non_omitted_nodes = dataset_basic_stats.get('num_non_omitted_nodes', None)
    
    return render(request, 'index.html', {'home': True,
                                          'num_categories_reached_goal': num_categories_reached_goal,
                                          'num_non_omitted_nodes': num_non_omitted_nodes})


def faq(request):
    return render(request, 'faq.html', {})


def discussion(request, short_name=None):
    if short_name:
        dataset = get_object_or_404(Dataset, short_name=short_name)
    else:
        dataset = None
    return render(request, 'discussion.html', {'dataset': dataset})


def login(request):
    next_url = request.GET.get('next', '')
    show_freesound = bool(settings.SOCIAL_AUTH_FREESOUND_KEY)
    show_github = bool(settings.SOCIAL_AUTH_GITHUB_KEY)
    show_facebook = bool(settings.SOCIAL_AUTH_FACEBOOK_KEY)
    show_google = bool(settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY)

    tvars = {'next': next_url,
             'show_freesound': show_freesound,
             'show_github': show_github,
             'show_facebook': show_facebook,
             'show_google': show_google
             }
    return render(request, 'login.html', tvars)


@partial
def registration(strategy, details, user=None, is_new=False, *args, **kwargs):
    backend = kwargs.get('current_partial').backend
    # new user
    if is_new:
        accepted = strategy.session_get('terms_accepted', None)
        if not accepted:
            strategy.session_set('social_username', details.get('username', ''))
            return redirect("registration-form", backend=backend)

        # user accepted, after user creation
        if user:
            user.profile.accepted_terms = True
            user.username = strategy.session_get('username', user.username)
            user.save()
        return

    # already registered user, check if they accepted terms
    else:
        # accepted = strategy.session_get('terms_accepted', None)
        # if user:
        #     if not user.profile.accepted_terms and not accepted:
        #         strategy.session_set('social_username', details.get('username', ''))
        #         return redirect("accept-terms-form", backend=backend)
        #     user.profile.accepted_terms = True
        #     user.username = strategy.session_get('username', user.username)
        #     user.save()
        return


def registration_form(request, backend):
    social_username = request.session.get('social_username')
    if request.method == 'POST':
        terms_accepted = request.POST.get('terms_accepted', False)
        request.session['terms_accepted'] = request.POST.get('terms_accepted')
        username = request.POST.get('username', social_username)
        username_already_exists = User.objects.filter(username=username).exists()
        if terms_accepted and not username_already_exists:
            request.session['username'] = username
            return redirect('social:complete', backend=backend)
        else:
            username = request.POST.get('username', social_username)
            return render(request, 'registration.html', {'backend': backend,
                                                         'terms_accepted': terms_accepted,
                                                         'social_username': username,
                                                         'username_already_exists': username_already_exists})
    return render(request, 'registration.html', {'backend': backend,
                                                 'terms_accepted': None,
                                                 'social_username': social_username,
                                                 'username_already_exists': None})


def terms_acceptance_form(request):
    if request.method == 'POST':
        terms_accepted = request.POST.get('terms_accepted', False)
        if terms_accepted:
            request.user.profile.accepted_terms = True
            request.user.save()
            return redirect(reverse('index'))
        else:
            return render(request, 'terms_acceptance.html', {'terms_accepted': terms_accepted})
    return render(request, 'terms_acceptance.html', {'terms_accepted': None})
