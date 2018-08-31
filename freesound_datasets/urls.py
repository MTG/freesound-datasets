from django.urls import include, re_path, path
from django.contrib import admin
from django.contrib.auth.views import logout
from freesound_datasets.views import *
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from datasets.views import get_access_token


urlpatterns = [
    re_path(r'^$', index, name='index'),
    re_path(r'^crash/$', crash_me, name='crash_me'),
    re_path(r'^login/$', login, name='login'),
    re_path(r'^logout/$', logout, {'next_page': '/'}, name='logout'),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^social/', include('social_django.urls', namespace='social')),
    re_path(r'^get-access-token/$', get_access_token, name='get_access_token'),
    re_path(r'^faq/', faq, name='faq'),
    re_path(r'^discussion/', discussion, name='discussion'),
    path('', include('datasets.urls')),
    path('', include('monitor.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        re_path(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    # We need to explicitly add staticfiles urls because we don't use runserver
    # https://docs.djangoproject.com/en/1.10/ref/contrib/staticfiles/#django.contrib.staticfiles.urls.staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
