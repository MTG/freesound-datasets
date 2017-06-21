from django.test import TestCase
from datasets.management.commands.generate_fake_data import add_taxonomy_nodes
from datasets import models


class TaxonomyTest(TestCase):

    def setUp(self):
        taxonomy = {
            "/m/0dgw9r" : {
                "id": "/m/0dgw9r",
                "name": "Sorted second",
                "description": "This item should be second if sorted",
                "child_ids": ["/m/09l8g"],
                "restrictions": ["abstact"],
                "citation_uri": "",
            },
            "/m/09l8g" : {
                "id": "/m/09l8g",
                "name": "Sorted first",
                "description": "This item should be first if sorted",
                "child_ids": [],
                "parent_ids": ["/m/0dgw9r"],
                "restrictions": ["omittedTT"],
                "citation_uri": "",
            }}

        self.taxobj = models.Taxonomy.objects.create(data=taxonomy)
        add_taxonomy_nodes(self.taxobj)
        
    def test_get_parents(self):
        parents = self.taxobj.get_parents("/m/09l8g")
        self.assertEqual(parents[0].node_id, "/m/0dgw9r")

        # The parent node has no parents
        parents = self.taxobj.get_parents("/m/0dgw9r")
        self.assertEqual(parents.count(), 0)
        
        
    def test_get_children(self):
        children = self.taxobj.get_children("/m/0dgw9r")
        self.assertEqual(children[0].node_id, "/m/09l8g")

    def test_get_all_nodes(self):
        """Check that we can get a sorted list of taxonomy notes"""
        nodes = self.taxobj.get_all_nodes()
        self.assertEqual(nodes[0].node_id, "/m/09l8g")
        self.assertEqual(nodes[1].node_id, "/m/0dgw9r")

