from django import template
from django.conf import settings
from django.core import urlresolvers
from django.utils.safestring import mark_safe
from django.conf import settings
from uuid import uuid4
import datetime
import re
import time

register = template.Library()


# Adapted from: http://blog.scur.pl/2012/09/highlighting-current-active-page-django/
@register.simple_tag(takes_context=True)
def current(context, url_name, return_value=' current', **kwargs):
    matches = current_url_equals(context, url_name, **kwargs)
    return return_value if matches else ''


# Adapted from: http://blog.scur.pl/2012/09/highlighting-current-active-page-django/
def current_url_equals(context, url_name, **kwargs):
    resolved = False
    try:
        resolved = urlresolvers.resolve(context.get('request').path)
    except:
        pass
    matches = resolved and (resolved.url_name == url_name or url_name in resolved.url_name)
    if matches and kwargs:
        for key in kwargs:
            kwarg = kwargs.get(key)
            resolved_kwarg = resolved.kwargs.get(key)
            if not resolved_kwarg or kwarg != resolved_kwarg:
                return False
    return matches


@register.simple_tag(takes_context=True)
def active_if_current(context, url_name, return_value=' current', **kwargs):
    if current(context, url_name, return_value, **kwargs):
        return 'active '
    else:
        return ''


@register.filter()
def timestamp_to_datetime(value):
    if not value or value is None:
        return None
    return datetime.datetime.fromtimestamp(value)


@register.filter()
def multiply(value, arg):
    return value*arg


@register.inclusion_tag('datasets/include_player_resources.html')
def load_sound_player_files():
    return


@register.inclusion_tag('datasets/player.html')
def sound_player(dataset, freesound_sound_id, player_size, normalization=None):
    sound = dataset.sounds.get(freesound_id=freesound_sound_id)
    sound_url = sound.extra_data['previews'][5:]
    spec_size = 'M' if player_size in ("mini", "small") else 'L'
    spectrogram_url = sound.get_image_url('spectrogram', spec_size)
    waveform_url = sound.get_image_url('waveform', 'M')
    loudness_target = settings.PLAYER_LOUDNESS_NORMALIZATION_TARGET
    max_ratio = settings.PLAYER_LOUDNESS_NORMALIZATION_MAX_RATIO
    loudness_method = settings.PLAYER_LOUDNESS_NORMALIZATION_METHOD
    loudness_normalization_ratio = sound.get_loudness_normalizing_ratio(loudness_method, loudness_target, max_ratio)
    return {'sound_url': sound_url,
            'freesound_id': freesound_sound_id,
            'spectrogram_url': spectrogram_url,
            'waveform_url': waveform_url,
            'player_size': player_size,
            'player_id': uuid4(),
            'normalization_method': loudness_method,
            'loudness_normalization_ratio': loudness_normalization_ratio,
            }


@register.simple_tag(takes_context=False)
def raven_install():
    sentry_full_dsn = settings.RAVEN_CONFIG['dsn']
    if sentry_full_dsn:
        sentry_dsn = ':'.join(sentry_full_dsn.split(':')[:2]) + '@' + sentry_full_dsn.split('@')[-1]
        return mark_safe('''
            <script src="https://cdn.ravenjs.com/3.25.1/raven.min.js" crossorigin="anonymous"></script>
            <script>
                Raven.config('{}').install();
            </script>
               '''.format(sentry_dsn))
    else:
        return ''
