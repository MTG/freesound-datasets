from django.test import TestCase
from datasets.management.commands.generate_fake_data import add_taxonomy_nodes
from datasets import models


class TaxonomyTest(TestCase):

    def setUp(self):
        taxonomy = {
            "/m/0dgw9r": {
                "id": "/m/0dgw9r",
                "name": "Sorted second",
                "description": "This item should be second if sorted",
                "child_ids": ["/m/09l8g"],
                "restrictions": ["abstact"],
                "citation_uri": "",
            },
            "/m/09l8g": {
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


class TaxonomyTestAdvanced(TestCase):

    def setUp(self):
        taxonomy = {
            "1": {
                "id": "1",
                "name": "1",
                "description": "This is a root category",
                "child_ids": ["2"],
                "restrictions": [],
                "citation_uri": "",
            },
            "2": {
                "id": "2",
                "name": "2",
                "description": "This is a simple non-root & non-leaf category",
                "child_ids": ["3"],
                "parent_ids": ["1"],
                "propagate_to_parent_ids": ["1"],
                "restrictions": [],
                "citation_uri": "",
            },
            "3": {
                "id": "3",
                "name": "3",
                "description": "This category has two parents",
                "child_ids": [],
                "parent_ids": ["2", "5"],
                "propagate_to_parent_ids": ["5"],
                "restrictions": [],
                "citation_uri": "",
            },
            "4": {
                "id": "4",
                "name": "4",
                "description": "This is a leaf category",
                "child_ids": [],
                "parent_ids": ["1"],
                "propagate_to_parent_ids": ["1"],
                "restrictions": [],
                "citation_uri": "",
            },
            "5": {
                "id": "5",
                "name": "5",
                "description": "This is a root category",
                "child_ids": ["3"],
                "restrictions": [],
                "citation_uri": "",
            },
        }

        self.taxobj = models.Taxonomy.objects.create(data=taxonomy)
        add_taxonomy_nodes(self.taxobj)

    def test_get_all_children(self):
        expected = ["2", "3", "4"]
        all_children_ids = self.taxobj.get_all_children("1").values_list('node_id', flat=True)
        self.assertCountEqual(all_children_ids, expected)
        self.assertSetEqual(set(all_children_ids), set(expected))

    def test_get_all_parents(self):
        expected = ["1", "2", "5"]
        all_parents_ids = self.taxobj.get_all_parents("3").values_list('node_id', flat=True)
        self.assertCountEqual(all_parents_ids, expected)
        self.assertSetEqual(set(all_parents_ids), set(expected))

    def test_get_all_propagate_to_parents(self):
        expected = ["5"]
        all_parents_ids = [n.node_id for n in self.taxobj.get_all_propagate_to_parents("3")]
        self.assertCountEqual(all_parents_ids, expected)
        self.assertSetEqual(set(all_parents_ids), set(expected))

    def test_get_all_propagate_from_children(self):
        expected = ["2", "4"]
        all_children_ids = [n.node_id for n in self.taxobj.get_all_propagate_from_children("1")]
        self.assertCountEqual(all_children_ids, expected)
        self.assertSetEqual(set(all_children_ids), set(expected))

    def test_get_hierarchy_paths(self):
        expected = sorted([["1", "2", "3"], ["5", "3"]])
        paths = sorted(self.taxobj.get_hierarchy_paths("3"))
        self.assertListEqual(expected, paths)

    def test_get_nodes_at_level_0(self):
        expected = sorted(["1", "5"])  # first level
        nodes = sorted([n.node_id for n in self.taxobj.get_nodes_at_level(0)])
        self.assertListEqual(expected, nodes)

    def test_get_nodes_at_level_1(self):
        expected = sorted(["2", "4", "3"])  # second level
        nodes = sorted([n.node_id for n in self.taxobj.get_nodes_at_level(1)])
        self.assertListEqual(expected, nodes)

    def test_get_nodes_at_level_2(self):
        expected = sorted(["3"])  # third level
        nodes = sorted([n.node_id for n in self.taxobj.get_nodes_at_level(2)])
        self.assertListEqual(expected, nodes)

