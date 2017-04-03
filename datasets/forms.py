from django import forms
from datasets.models import DatasetRelease, Vote


class DatasetReleaseForm(forms.ModelForm):
    max_number_of_sounds = forms.IntegerField(required=False)

    class Meta:
        model = DatasetRelease
        fields = ['release_tag', 'type']


class PresentNotPresentUnsureForm(forms.Form):
    vote = forms.ChoiceField(
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ('1', 'Present',),
            ('0.5', 'Slightly present',),
            ('-1', 'Not Present',),
            ('0', 'Unsure',),
        ),
    )
    annotation_id = forms.IntegerField(
        required=True,
        widget=forms.HiddenInput,
    )
    visited_sound = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput,
    )

