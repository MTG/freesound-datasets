from django.contrib import admin
from datasets.models import Dataset, Sound, Annotation, Vote, Taxonomy, DatasetRelease, TaxonomyNode


class TaxonomyNodeAdmin(admin.ModelAdmin):
    fields = ('node_id', 'name', 'description', 'citation_uri', 'faq', 'omitted')


admin.site.register(Dataset)
admin.site.register(Sound)
admin.site.register(Annotation)
admin.site.register(Vote)
admin.site.register(Taxonomy)
admin.site.register(DatasetRelease)
admin.site.register(TaxonomyNode, TaxonomyNodeAdmin)
