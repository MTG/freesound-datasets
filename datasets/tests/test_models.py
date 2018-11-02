from django.test import Client, TestCase
from datasets import models
from datasets.management.commands.generate_fake_data import create_sounds, create_users, create_candidate_annotations, \
    add_taxonomy_nodes, VALID_FS_IDS, get_dataset


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


class DatasetTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        # For these tests we create only one sound and one candidate annotation
        add_taxonomy_nodes(models.Taxonomy.objects.get())
        create_sounds('fsd', 1)
        create_users(2)
        create_candidate_annotations('fsd', 1)
        candidate_annotation = models.CandidateAnnotation.objects.first()
        users = models.User.objects.all()
        self.dataset = models.Dataset.objects.get(short_name='fsd')

        # create 2 votes for the candidate annotations (it should create ground truth annotations)
        for user in users:
            self.dataset.maintainers.add(user)
            models.Vote.objects.create(
                created_by=user,
                vote=1.0,
                visited_sound=False,
                candidate_annotation_id=candidate_annotation.id,
                test='AP',
                from_test_page=True,
                from_task='AD',
            )
        self.dataset.save()

    def test_get_candidate_annotations(self):
        expected = models.CandidateAnnotation.objects.first()
        candidate_annotation = self.dataset.candidate_annotations.first()
        self.assertEqual(expected, candidate_annotation)

    def test_get_ground_truth_annotations(self):
        # check that there is one (non propagated) ground truth annotation
        self.assertEqual(self.dataset.ground_truth_annotations.filter(from_propagation=False).count(), 1)

    def test_num_sounds(self):
        self.assertEqual(self.dataset.num_sounds, 1)

    def test_num_sounds_with_candidate(self):
        self.assertEqual(self.dataset.num_sounds_with_candidate, 1)

    def test_num_validated_annotations(self):
        self.assertEqual(self.dataset.num_validated_annotations, 1)

    def test_percentage_validated_annotations(self):
        self.assertEqual(self.dataset.percentage_validated_annotations, 100.0)

    def test_num_verified_annotations(self):
        self.assertEqual(self.dataset.num_verified_annotations, 1)

    def test_percentage_verified_annotations(self):
        self.assertEqual(self.dataset.percentage_verified_annotations, 100.0)

    def test_num_user_contributions(self):
        self.assertEqual(self.dataset.num_user_contributions, 2)

    def test_get_categories_to_validate(self):
        user = models.User.objects.first()
        self.assertEqual(self.dataset.get_categories_to_validate(user).count(), 0)

    def test_user_can_annotate(self):
        user = models.User.objects.first()
        node = models.CandidateAnnotation.objects.first().taxonomy_node
        self.assertEqual(self.dataset.user_can_annotate(node.node_id, user), False)

    def test_num_votes_with_value(self):
        node = models.CandidateAnnotation.objects.first().taxonomy_node
        self.assertEqual(self.dataset.num_votes_with_value(node.node_id, 1.0), 2)

    def test_user_is_maintainer(self):
        user = models.User.objects.first()
        self.assertEqual(self.dataset.user_is_maintainer(user), True)
