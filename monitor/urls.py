from django.conf.urls import url, include
from monitor.views import *


urlpatterns = [
    url(r'^(?P<short_name>[^\/]+)/monitor_categories/$', monitor_categories, name='monitor-categories'),
]
