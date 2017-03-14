from django.conf.urls import url

from datasets import views

urlpatterns = [
    url(r'new-taxonomy$', views.upload_taxonomy, name='upload-taxonomy'),
]
