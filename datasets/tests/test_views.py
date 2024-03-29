from django.test import Client, TestCase
from datasets.models import *
from datasets.views import *
from datasets.forms import *
from datasets.management.commands.generate_fake_data import create_sounds, create_users, create_candidate_annotations, \
    add_taxonomy_nodes, VALID_FS_IDS, get_dataset
from datasets.tasks import generate_release_index


class ContributeTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']
    
    def setUp(self):
        add_taxonomy_nodes(Taxonomy.objects.get())
        create_sounds('fsd', 1)
        create_users(1)
        create_candidate_annotations('fsd', 1)
           
    def test_save_contribute_validate_annotations_category(self):
        dataset = Dataset.objects.get(short_name='fsd')
        
        # get a node id with at least one annotation
        node_id = CandidateAnnotation.objects.filter(sound_dataset__gt=0)[0].value
        annotations = dataset.non_validated_annotations_per_taxonomy_node(node_id)
        annotation_object_id = annotations.values_list('id', flat=True)[0]
        
        # create form data with one annotation vote form
        form_data = {'form-MAX_NUM_FORMS': '1000', 
                     'category_id': node_id, 
                     'form-INITIAL_FORMS': 1, 
                     'form-TOTAL_FORMS': 2,
                     'comment': '',
                     'dataset': '1',
                     'form-0-visited_sound': 'False',
                     'form-0-annotation_id': str(annotation_object_id),
                     'form-0-vote': '1',
                     'from_task': 'AD'
                    }     
            
        self.client.login(username='username_0', password='123456')
        
        # check the response an that a vote is added in the database
        response = self.client.post(reverse('save-contribute-validate-annotations-per-category'), data=form_data) 
        self.assertEquals(response.status_code, 200)
        self.assertEquals(Vote.objects.filter(candidate_annotation_id=annotation_object_id).count(), 1)
        
        # check that a second vote is not added, or modified
        form_data['form-0-vote'] = '-1'
        self.client.post(reverse('save-contribute-validate-annotations-per-category'), data=form_data)
        self.assertEquals(Vote.objects.filter(candidate_annotation_id=annotation_object_id).count(), 1)
        self.assertEquals(Vote.objects.get(candidate_annotation_id=annotation_object_id).vote, 1)


class AdvancedContributeTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        add_taxonomy_nodes(Taxonomy.objects.get())
        create_users(1)
        user = User.objects.first()
        # creates 24 sounds with length [0.3, 10] and [10, 20], and their annotations
        dataset = get_dataset('fsd')
        node = dataset.taxonomy.taxonomynode_set.first()
        num_current_sounds = Sound.objects.all().count()
        fsids = [VALID_FS_IDS[i % len(VALID_FS_IDS)] for i in range(0, 24)]
        with transaction.atomic():
            for count, fsid in enumerate(fsids):
                sound = Sound.objects.create(
                    name='Freesound sound #{0}'.format(count + num_current_sounds),
                    freesound_id=fsid,
                    extra_data={
                        'duration': 0.3 + 5*random.random() if count < 12 else 10 + 10*random.random(),
                        'previews': 'https://freesound.org/data/previews/188/188440_3399958-hq.ogg'
                    }
                )
                sound_dataset = SoundDataset.objects.create(
                    dataset=dataset,
                    sound=sound
                )
                candidate_annotation = CandidateAnnotation.objects.create(
                    sound_dataset=sound_dataset,
                    taxonomy_node=node,
                    type='AU',
                    algorithm='Fake algorithm name',
                    created_by=user
                )
                candidate_annotation.update_priority_score()

    def test_first_page_duration(self):
        # test that the first page gives only 12 sounds with duration [0.3, 10]
        dataset = Dataset.objects.get(short_name='fsd')
        node = TaxonomyNode.objects.filter(candidate_annotations__gt=0)[0]
        node_id = node.node_id
        node_url = node.url_id
        self.client.login(username='username_0', password='123456')

        expected_annotation_ids = sorted(CandidateAnnotation.objects
                                                            .filter(sound_dataset__sound__extra_data__duration__lt=10)
                                                            .values_list('id', flat=True))
        response = self.client.get(reverse('contribute-validate-annotations-category',
                                           kwargs={
                                               'node_id': node_url,
                                                'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)
        selected_candidates = sorted([form[0].id for form in response.context['annotations_forms']])
        self.assertListEqual(expected_annotation_ids, selected_candidates)

    def test_second_page_duration(self):
        # test that the second page gives only 12 sounds with duration [10, 20]
        dataset = Dataset.objects.get(short_name='fsd')
        node = TaxonomyNode.objects.filter(candidate_annotations__gt=0)[0]
        node_id = node.node_id
        node_url = node.url_id
        self.client.login(username='username_0', password='123456')

        # get the candidates first page
        response = self.client.get(reverse('contribute-validate-annotations-category',
                                           kwargs={
                                                'node_id': node_url,
                                                'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)
        selected_candidates = [form[0].id for form in response.context['annotations_forms']]

        # create form data with the 12 annotation vote forms
        form_data = {'form-MAX_NUM_FORMS': '1000',
                     'category_id': node_id,
                     'form-INITIAL_FORMS': 12,
                     'form-TOTAL_FORMS': 13,
                     'comment': '',
                     'dataset': '1',
                     'from_task': 'AD'
                    }
        for idx, candidate_id in enumerate(selected_candidates):
            form_data.update({
                'form-{}-visited_sound'.format(idx): 'False',
                'form-{}-annotation_id'.format(idx): str(candidate_id),
                'form-{}-vote'.format(idx): str(random.choice([-1, 0, 0.5, 1])),
            })

        # submit form
        response = self.client.post(reverse('save-contribute-validate-annotations-per-category'), data=form_data)
        self.assertEquals(response.status_code, 200)

        # get the candidates second page
        response = self.client.get(reverse('contribute-validate-annotations-category',
                                           kwargs={
                                                'node_id': node_url,
                                                'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

        # check that the selected candidates correspond to the 12 sounds with duration > 10 sec
        expected_annotation_ids = sorted(CandidateAnnotation.objects
                                         .filter(sound_dataset__sound__extra_data__duration__gt=10)
                                         .values_list('id', flat=True))
        selected_candidates = sorted([form[0].id for form in response.context['annotations_forms']])
        self.assertListEqual(expected_annotation_ids, selected_candidates)


def create_release():
    release = DatasetRelease.objects.create(release_tag='test', type='IN')
    release.dataset = Dataset.objects.get(short_name='fsd')
    release.save()


class DatasetReleaseTests(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        add_taxonomy_nodes(Taxonomy.objects.get())
        create_sounds('fsd', 10)
        create_users(1)
        user = User.objects.first()
        dataset = Dataset.objects.get(short_name='fsd')
        dataset.maintainers.add(user)
        dataset.save()
        create_candidate_annotations('fsd', 20)
        # create ground truth annotations
        for candidate_annotation in CandidateAnnotation.objects.all():
            gt_annotation, created = GroundTruthAnnotation.objects.get_or_create(
                start_time=candidate_annotation.start_time,
                end_time=candidate_annotation.end_time,
                ground_truth=candidate_annotation.ground_truth,
                created_by=candidate_annotation.created_by,
                sound_dataset=candidate_annotation.sound_dataset,
                taxonomy_node=candidate_annotation.taxonomy_node,
                from_propagation=False)
            gt_annotation.from_candidate_annotations.add(candidate_annotation)

        # add preview url for sounds
        sounds = Sound.objects.all()
        with transaction.atomic():
            for sound in sounds:
                sound.extra_data['previews'] = 'https://freesound.org/data/previews/188/188440_3399958-hq.ogg'
                sound.save()

        self.client.login(username='username_0', password='123456')

    def test_create_release_launch(self):
        # create release
        form_data = {
            'release_tag': ['test'],
            'type': ['IN'],
            'max_number_of_sounds': ['']
        }

        response = self.client.post(reverse('dataset-explore',
                                            kwargs={
                                                'short_name': 'fsd'
                                            }),
                                    data=form_data)
        self.assertEquals(response.status_code, 302)  # http redirect

        # check that the release has been correctly created
        release = DatasetRelease.objects.first()
        self.assertEqual(release.release_tag, 'test')
        self.assertEqual(release.type, 'IN')

    def test_create_release(self):
        create_release()
        release = DatasetRelease.objects.get(release_tag='test')
        dataset = Dataset.objects.get(short_name='fsd')
        generate_release_index(dataset.id, release.id)

        self.assertSetEqual(set(release.ground_truth_annotations.all()),
                            set(GroundTruthAnnotation.objects.all()))

    def test_release_explore(self):
        create_release()

        # release page
        response = self.client.get(reverse('dataset-release',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test'
                                           }))

        self.assertEquals(response.status_code, 200)
        self.assertEqual(response.context['release'].release_tag, 'test')

    def test_download_release(self):
        create_release()

        # access download page
        response = self.client.get(reverse('download-release',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test'
                                           }))
        self.assertEqual(response.status_code, 200)

    def test_delete_release(self):
        create_release()

        # delete release and then check that it does not exist anymore
        response = self.client.get(reverse('delete-release',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test'
                                           }))

        self.assertEqual(list(DatasetRelease.objects.all()), [])
        self.assertEquals(response.status_code, 302)  # http redirect

    def test_release_table(self):
        create_release()
        release = DatasetRelease.objects.get(release_tag='test')
        dataset = Dataset.objects.get(short_name='fsd')

        generate_release_index(dataset.id, release.id)

        response = self.client.get(reverse('release-table',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test'
                                           }))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['release'].num_sounds,
                         Sound.objects.exclude(sounddataset__ground_truth_annotations=None).count())
        self.assertEqual(response.context['release'].num_annotations, 20)

    def test_release_taxonomy_table(self):
        create_release()

        response = self.client.get(reverse('release-taxonomy-table',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test'
                                           }))
        self.assertEqual(response.status_code, 200)

    def test_release_taxonomy_node(self):
        create_release()
        ground_truth_annotation = GroundTruthAnnotation.objects.first()
        release = DatasetRelease.objects.get(release_tag='test')
        release.ground_truth_annotations.add(ground_truth_annotation)

        response = self.client.get(reverse('release-taxonomy-node',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'release_tag': 'test',
                                               'node_id': ground_truth_annotation.taxonomy_node.url_id
                                           }))
        self.assertEqual(response.status_code, 200)

    def test_report_ground_truth_annotation(self):
        create_release()
        ground_truth_annotation = GroundTruthAnnotation.objects.first()
        ground_truth_annotation_pk = ground_truth_annotation.pk
        release = DatasetRelease.objects.get(release_tag='test')
        release.ground_truth_annotations.add(ground_truth_annotation)

        # report a ground truth and check that it is in the db
        form_data = {
            'annotation_id': ground_truth_annotation_pk,
            'report_or_undo': 'report'
        }

        response = self.client.post(reverse('report-ground-truth-annotation',
                                            kwargs={
                                                'short_name': 'fsd',
                                                'release_tag': 'test'
                                            }),
                                    data=form_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GroundTruthAnnotation.objects.get(pk=ground_truth_annotation_pk).errorreport_set.count(), 1)


class Basic200ResponseTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']

    def setUp(self):
        add_taxonomy_nodes(Taxonomy.objects.get())
        create_sounds('fsd', 10)
        create_users(5)
        create_candidate_annotations('fsd', 20)

        # add preview url for sounds
        sounds = Sound.objects.all()
        with transaction.atomic():
            for sound in sounds:
                sound.extra_data['previews'] = 'https://freesound.org/data/previews/188/188440_3399958-hq.ogg'
                sound.save()

        self.node_with_candidates = CandidateAnnotation.objects.first().taxonomy_node
        self.client.login(username='username_0', password='123456')

    def test_dataset(self):
        response = self.client.get(reverse('dataset',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_explore(self):
        response = self.client.get(reverse('dataset-explore',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_taxonomy_tree(self):
        response = self.client.get(reverse('taxonomy-tree',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_taxonomy_table(self):
        response = self.client.get(reverse('taxonomy-table',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_state_table(self):
        response = self.client.get(reverse('state-table',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_taxonomy_node(self):
        response = self.client.get(reverse('dataset-explore-taxonomy-node',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'node_id': self.node_with_candidates.url_id
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_contribute(self):
        response = self.client.get(reverse('contribute',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_contribute_validate_annotations(self):
        response = self.client.get(reverse('contribute-validate-annotations-category',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'node_id': self.node_with_candidates.url_id
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_contribute_validate_annotations_easy(self):
        response = self.client.get(reverse('contribute-validate-annotations-category-beginner',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_contribute_validate_annotations_all(self):
        response = self.client.get(reverse('contribute-validate-annotations-all',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_contribute_validate_annotations_category(self):
        response = self.client.get(reverse('contribute-validate-annotations-category',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'node_id': self.node_with_candidates.url_id
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_choose_category(self):
        response = self.client.get(reverse('choose_category',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_taxonomy_table_choose(self):
        response = self.client.get(reverse('dataset_taxonomy_table_choose',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_taxonomy_table_search(self):
        response = self.client.get(reverse('taxonomy-table-search',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_dataset_taxonomy_table_search_all(self):
        response = self.client.get(reverse('taxonomy-table-search-all',
                                           kwargs={
                                               'short_name': 'fsd'
                                           }))
        self.assertEquals(response.status_code, 200)

    def test_get_mini_node_info(self):
        response = self.client.get(reverse('get-mini-node-info',
                                           kwargs={
                                               'short_name': 'fsd',
                                               'node_id': self.node_with_candidates.url_id
                                           }))
        self.assertEquals(response.status_code, 200)
    