from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import JSONField

class Taxonomy(models.Model):
    """A model that handles the whole taxonomy"""
    data = JSONField()
    created = models.DateTimeField(auto_now_add=True)

    def get_root_node(self):
        parent = self.data[0]['id']
        child = None
        while parent:
            child = parent
            parent = self.get_one_parent(parent)
        return child

    def get_one_parent(self, ontology_id):
        for e in self.data:
            if ontology_id in e['child_ids']:
                return e['id']

    def get_children(self, ontology_id):
        for e in self.data:
            if e['id'] == ontology_id:
                return e['child_ids']
        return None

    def get_element_at_id(self, ontology_id):
        for e in self.data:
            if e['id'] == ontology_id:
                return e
        return None


