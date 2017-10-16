from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from datasets.models import Dataset


@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/')
def crash_me(request):
    raise Exception('Everything is under control')


def index(request):
    return render(request, 'index.html', {})


def faq(request):
    return render(request, 'faq.html', {})


def discussion(request):
    return render(request, 'discussion.html', {})


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
