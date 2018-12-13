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


class GroundTruthAnnotationTest(TestCase):

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
                "parent_ids": ["5"],
                "propagate_to_parent_ids": ["5"],
                "restrictions": [],
                "citation_uri": "",
            },
            "5": {
                "id": "5",
                "name": "5",
                "description": "This is a root category",
                "child_ids": ["3", "4"],
                "restrictions": [],
                "citation_uri": "",
            },
        }

        self.taxobj = models.Taxonomy.objects.create(data=taxonomy)
        add_taxonomy_nodes(self.taxobj)

        models.Dataset.objects.create(short_name='fsd',
                                      taxonomy=self.taxobj)

        create_sounds('fsd', 1)
        create_users(1)
        self.sound = models.Sound.objects.first()
        self.user = models.User.objects.first()

        self.taxonomy_node = self.taxobj.get_element_at_id("3")  # a children node
        self.second_taxonomy_node = self.taxobj.get_element_at_id("4")  # a children node
        # a root node which is propagated from the two nodes above
        self.taxonomy_node_to_propagate_to = self.taxobj.get_element_at_id("5")

        create_candidate_annotations('fsd', 1)
        self.candidate_annotation = models.CandidateAnnotation.objects.create(
            sound_dataset=self.sound.sounddataset_set.first(),
            type='AU',
            algorithm='Fake algorithm name',
            taxonomy_node=self.taxonomy_node,
            ground_truth=1.0,
        )

        self.users = models.User.objects.all()
        self.dataset = models.Dataset.objects.get(short_name='fsd')
        # self.candidate_annotation = models.CandidateAnnotation.objects.first()
        # self.candidate_annotation.ground_truth = 1.0
        self.candidate_annotation.save()

        self.gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=1.0,
            created_by=self.user,
            sound_dataset=self.sound.sounddataset_set.first(),
            taxonomy_node=self.taxonomy_node)
        self.gt_annotation.from_candidate_annotations.add(self.candidate_annotation)

    def test_propagate_ground_truth_annotations(self):
        self.gt_annotation.propagate_annotation()

        # check that a ground truth annotation was created for taxonomy node with id 5
        self.assertEqual(1, self.taxonomy_node_to_propagate_to.num_ground_truth_annotations)

    def test_propagate_ground_truth_annotations_does_not_create_new_one(self):
        existing_gt_value = 0.5
        # first create a ground truth annotation in the parent node
        existing_gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=existing_gt_value,
            created_by=self.user,
            sound_dataset=self.sound.sounddataset_set.first(),
            taxonomy_node=self.taxonomy_node_to_propagate_to,
        )
        existing_gt_annotation.from_candidate_annotations.add(self.candidate_annotation)
        self.gt_annotation.propagate_annotation()

        # check that it did not create another ground truth annotation, neither altered it
        num_gt_annotations = models.GroundTruthAnnotation.objects.filter(
            taxonomy_node=self.taxonomy_node_to_propagate_to).count()
        self.assertEqual(1, num_gt_annotations)
        gt_annotation = models.GroundTruthAnnotation.objects.filter(
            taxonomy_node=self.taxonomy_node_to_propagate_to).first()
        self.assertEqual(existing_gt_value, gt_annotation.ground_truth)

    def test_propagate_ground_truth_annotations_expert(self):
        existing_gt_value = 0.5
        expected_value_after_propagation = 1.0
        # first create a ground truth annotation in the parent node
        existing_gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=existing_gt_value,
            created_by=self.user,
            sound_dataset=self.sound.sounddataset_set.first(),
            taxonomy_node=self.taxonomy_node_to_propagate_to,
        )
        existing_gt_annotation.from_candidate_annotations.add(self.candidate_annotation)

        self.gt_annotation.propagate_annotation(from_expert=True)

        # check that it did not create another ground truth annotation, and did altered its ground truth value
        num_gt_annotations = models.GroundTruthAnnotation.objects.filter(
            taxonomy_node=self.taxonomy_node_to_propagate_to).count()
        self.assertEqual(1, num_gt_annotations)
        gt_annotation = models.GroundTruthAnnotation.objects.filter(
            taxonomy_node=self.taxonomy_node_to_propagate_to).first()
        self.assertEqual(expected_value_after_propagation, gt_annotation.ground_truth)

    def test_unpropagate_ground_truth_annotation(self):
        # first create a ground truth annotation in the parent node
        existing_gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=1,
            created_by=self.user,
            sound_dataset=self.sound.sounddataset_set.first(),
            taxonomy_node=self.taxonomy_node_to_propagate_to,
        )
        existing_gt_annotation.from_candidate_annotations.add(self.candidate_annotation)

        # unpropagate gt annotation
        self.gt_annotation.unpropagate_annotation(self.candidate_annotation)

        # check that the parent gt annotation was deleted
        self.assertEqual(0, models.GroundTruthAnnotation.objects.filter(
                                taxonomy_node=self.taxonomy_node_to_propagate_to).count())

    def test_unpropagate_ground_truth_annotation_does_not_remove_ground_truth_if_multiple_children_annotations(self):
        # first create candidate
        second_candidate_annotation = models.CandidateAnnotation.objects.create(
            sound_dataset=self.sound.sounddataset_set.first(),
            type='AU',
            algorithm='Fake algorithm name',
            taxonomy_node=self.second_taxonomy_node,
            ground_truth=1,
        )
        # create ground truth annotation in one of the children node and propagate it
        existing_gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=1,
            created_by=self.user,
            sound_dataset=self.sound.sounddataset_set.first(),
            taxonomy_node=self.second_taxonomy_node,
        )
        existing_gt_annotation.from_candidate_annotations.add(second_candidate_annotation)
        existing_gt_annotation.propagate_annotation()

        # unpropagate the ground truth annotation in the other children node
        self.gt_annotation.unpropagate_annotation(self.candidate_annotation)

        # check that the propagated gt annotation was not removed
        self.assertEqual(
            1,
            models.GroundTruthAnnotation.objects.filter(taxonomy_node=self.taxonomy_node_to_propagate_to).count()
        )


class VoteTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        # For these tests we create only one sound and one candidate annotation
        add_taxonomy_nodes(models.Taxonomy.objects.get())
        create_sounds('fsd', 1)
        create_users(2)
        create_candidate_annotations('fsd', 1)
        self.users = models.User.objects.all()
        self.dataset = models.Dataset.objects.get(short_name='fsd')
        self.candidate_annotation = models.CandidateAnnotation.objects.first()

    def test_save_votes_create_ground_truth_annotation(self):
        for user in self.users:
            models.Vote.objects.create(
                created_by=user,
                vote=1.0,
                candidate_annotation=self.candidate_annotation,
                )
        # check that one ground truth annotation was created (only not propagated), and that his properties are ok
        ground_truth_annotations = models.GroundTruthAnnotation.objects.filter(from_propagation=False)
        self.assertEqual(1, ground_truth_annotations.count())
        ground_truth_annotation = ground_truth_annotations.first()
        self.assertEqual(self.candidate_annotation, ground_truth_annotation.from_candidate_annotations.first())
        self.assertEqual(self.candidate_annotation.taxonomy_node, ground_truth_annotation.taxonomy_node)
        self.assertEqual(1.0, ground_truth_annotation.ground_truth)
        # check that the candidate annotation has ground truth field set
        self.assertEqual(1.0, self.candidate_annotation.ground_truth)

    def test_save_one_expert_vote_creates_ground_truth_annotation(self):
        user = self.users.first()
        models.Vote.objects.create(
            created_by=user,
            vote=1.0,
            candidate_annotation=self.candidate_annotation,
            from_expert=True,
        )
        # check that one ground truth annotation was created (only not propagated), and that his properties are ok
        ground_truth_annotations = models.GroundTruthAnnotation.objects.filter(from_propagation=False)
        self.assertEqual(1, ground_truth_annotations.count())
        ground_truth_annotation = ground_truth_annotations.first()
        self.assertEqual(self.candidate_annotation, ground_truth_annotation.from_candidate_annotations.first())
        self.assertEqual(self.candidate_annotation.taxonomy_node, ground_truth_annotation.taxonomy_node)
        self.assertEqual(1.0, ground_truth_annotation.ground_truth)
        # check that the candidate annotation has ground truth field set
        self.assertEqual(1.0, self.candidate_annotation.ground_truth)

    def test_save_one_expert_PNP_vote_modifies_existing_ground_truth_annotation(self):
        user = self.users.first()
        gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=1.0,
            created_by=user,
            sound_dataset=self.candidate_annotation.sound_dataset,
            taxonomy_node=self.candidate_annotation.taxonomy_node,
        )
        gt_annotation.from_candidate_annotations.add(self.candidate_annotation)

        models.Vote.objects.create(
            created_by=user,
            vote=0.5,
            candidate_annotation=self.candidate_annotation,
            from_expert=True,
        )
        # check that one ground truth annotation was created (only not propagated), and that his properties are ok
        ground_truth_annotations = models.GroundTruthAnnotation.objects.filter(from_propagation=False)
        self.assertEqual(1, ground_truth_annotations.count())
        ground_truth_annotation = ground_truth_annotations.first()
        self.assertEqual(self.candidate_annotation, ground_truth_annotation.from_candidate_annotations.first())
        self.assertEqual(self.candidate_annotation.taxonomy_node, ground_truth_annotation.taxonomy_node)
        self.assertEqual(0.5, ground_truth_annotation.ground_truth)
        # check that the candidate annotation has ground truth field set
        self.assertEqual(0.5, self.candidate_annotation.ground_truth)

    def test_save_one_expert_vote_propagates_ground_truth_annotation(self):
        pass
        # TODO: this test needs more controllable data such as the one in GroundTruthAnnotationTest setUp taxonomy

    def test_save_one_NP_expert_vote_deletes_ground_truth_annotation(self):
        user = self.users.first()
        gt_annotation = models.GroundTruthAnnotation.objects.create(
            ground_truth=1.0,
            created_by=user,
            sound_dataset=self.candidate_annotation.sound_dataset,
            taxonomy_node=self.candidate_annotation.taxonomy_node,
        )
        gt_annotation.from_candidate_annotations.add(self.candidate_annotation)

        models.Vote.objects.create(
            created_by=user,
            vote=-1,
            candidate_annotation=self.candidate_annotation,
            from_expert=True,
        )
        # check that one ground truth annotation was created (only not propagated), and that his properties are ok
        ground_truth_annotations = models.GroundTruthAnnotation.objects.filter(from_propagation=False)
        self.assertEqual(0, ground_truth_annotations.count())
        # check that the candidate annotation has ground truth field set
        self.assertEqual(-1, self.candidate_annotation.ground_truth)

    def test_save_one_NP_expert_vote_deletes_propagated_ground_truth_annotations(self):
        pass
        # TODO: this test needs more controllable data such as the one in GroundTruthAnnotationTest setUp taxonomy


class CandidateAnnotationTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        # For these tests we create only one sound and one candidate annotation
        add_taxonomy_nodes(models.Taxonomy.objects.get())
        create_sounds('fsd', 1)
        create_users(5)
        create_candidate_annotations('fsd', 1)
        self.candidate_annotation = models.CandidateAnnotation.objects.first()
        self.users = models.User.objects.all()
        self.dataset = models.Dataset.objects.get(short_name='fsd')
        for user in self.users:
            self.dataset.maintainers.add(user)
        self.dataset.save()

    def create_vote(self, user, vote_value, test, from_task='AD', from_expert=False):
        models.Vote.objects.create(
            created_by=user,
            vote=vote_value,
            visited_sound=False,
            candidate_annotation_id=self.candidate_annotation.id,
            test=test,
            from_test_page=True,
            from_task='AD',
            from_expert=from_expert,
        )

    def test_ground_truth_state_wo_expert_votes_two_PP(self):
        for user in self.users[:2]:
            self.create_vote(user, 1.0, 'AP')
        self.assertEqual(1, self.candidate_annotation.ground_truth_state)

    def test_ground_truth_state_wo_expert_votes_one_PP_one_PNP(self):
        votes = [1.0, 0.5]
        for idx, user in enumerate(self.users[:2]):
            self.create_vote(user, votes[idx], 'AP')
        self.assertEqual(None, self.candidate_annotation.ground_truth_state)

    def test_ground_truth_state_wo_expert_votes_one_PP_two_PNP_one_U_one_NP(self):
        votes = [1.0, 0.5, 0.5, 0, -1.0]
        for idx, user in enumerate(self.users):
            self.create_vote(user, votes[idx], 'AP')
        self.assertEqual(0.5, self.candidate_annotation.ground_truth_state)

    def test_ground_truth_state_does_not_count_FA_votes(self):
        votes = [1.0, 1.0, 1.0]
        for idx, user in enumerate(self.users[:3]):
            self.create_vote(user, votes[idx], 'FA')
        self.assertEqual(None, self.candidate_annotation.ground_truth_state)

    def test_ground_truth_state_two_NP_and_one_PP_expert(self):
        votes = [-1.0, -1.0]
        for idx, user in enumerate(self.users[:2]):
            self.create_vote(user, votes[idx], 'AP')
        self.create_vote(self.users[2], 1.0, 'UN', from_task='CU', from_expert=True)
        self.assertEqual(1.0, self.candidate_annotation.ground_truth_state)

    def test_ground_truth_state_last_expert_vote_wins(self):
        votes = [0, 0, 1.0]
        for idx, user in enumerate(self.users[:3]):
            self.create_vote(user, votes[idx], 'UN', from_task='CU', from_expert=True)
        self.assertEqual(1.0, self.candidate_annotation.ground_truth_state)

    # TODO: add test priority score
