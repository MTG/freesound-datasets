from django import forms
from datasets.models import DatasetRelease


class DatasetReleaseForm(forms.ModelForm):
    max_number_of_sounds = forms.IntegerField(required=False)

    class Meta:
        model = DatasetRelease
        fields = ['release_tag', 'type']
