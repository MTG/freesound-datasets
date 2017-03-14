import json

from django import forms
from django.conf import settings

class JsonForm(forms.Form):
    json_file = forms.FileField()

    def clean_json_file(self):
        # Validate that is a json file and size is less than the specified
        content = self.cleaned_data['json_file']
        if content._size > settings.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(\
                    'Please keep filesize under %s. Current filesize %s' % (
                        filesizeformat(settings.MAX_UPLOAD_SIZE),\
                                filesizeformat(content._size)))


        new_items = json.loads(content.read().decode('utf-8'))
        if not isinstance(new_items, list):
            raise forms.ValidationError('The Json file must contain a list of elements')
        return new_items

