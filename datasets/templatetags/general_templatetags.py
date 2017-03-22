from django import template
from django.core import urlresolvers
import datetime
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
    matches = resolved and resolved.url_name == url_name
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

