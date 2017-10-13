from django.contrib import admin
from datasets.models import Dataset, Sound, Annotation, Vote, Taxonomy, DatasetRelease, TaxonomyNode

admin.site.register(Dataset)
admin.site.register(Sound)
admin.site.register(Annotation)
admin.site.register(Vote)
admin.site.register(Taxonomy)
admin.site.register(DatasetRelease)
admin.site.register(TaxonomyNode)
