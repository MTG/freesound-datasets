from django import forms
from datasets.models import DatasetRelease, CategoryComment


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
            ('1', 'Present and predominant',),
            ('0.5', 'Present but not predominant',),
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


class CategoryCommentForm(forms.ModelForm):

    class Meta:
        model = CategoryComment
        fields = ['comment', 'category_id', 'dataset']
        widgets = {
            'comment': forms.Textarea(attrs={
                'cols': 80, 'rows': 3,
                'placeholder': 'Add here any general comments you want to make about this category'}),
            'category_id': forms.HiddenInput,
            'dataset_id': forms.HiddenInput,
        }
