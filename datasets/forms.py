from django.forms import ModelForm
from datasets.models import DatasetRelease


class DatasetReleaseForm(ModelForm):
    class Meta:
        model = DatasetRelease
        fields = ['release_tag']
