from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.views import logout
from freesound_datasets.views import *
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from datasets.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^crash/$', crash_me, name='crash_me'),
    url(r'^login/$', login, name='login'),
    url(r'^logout/$', logout, {'next_page': '/'}, name='logout'),
    url(r'^admin/', admin.site.urls),
    url(r'^social/', include('social_django.urls', namespace='social')),
    url(r'^get-access-token/$', get_access_token, name='get_access_token'),
    url(r'^faq/', faq, name='faq'),
    url(r'^discussion/', discussion, name='discussion'),
    url(r'', include('datasets.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    # We need to explicitly add staticfiles urls because we don't use runserver
    # https://docs.djangoproject.com/en/1.10/ref/contrib/staticfiles/#django.contrib.staticfiles.urls.staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
