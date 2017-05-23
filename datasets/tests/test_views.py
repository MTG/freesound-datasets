from django.test import Client, TestCase
from datasets.models import *
from datasets.views import *
from datasets.forms import *
from datasets.management.commands.generate_fake_data import create_sounds, create_users, create_annotations


class ContributeTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']
    
    def setUp(self):
        create_sounds('fsd', 1)
        create_users(1)
        create_annotations('fsd', 1)
        
    def test_save_contribute_validate_annotations_category(self):
        dataset = Dataset.objects.get(short_name='fsd')
        
        # get a node id with at least one annotation
        node_id = Annotation.objects.filter(sound_dataset__gt=0)[0].value
        annotations = dataset.non_validated_annotations_per_taxonomy_node(node_id)
        annotation_object_id = annotations.values_list('id', flat=True)[0]
        
        # create form data with one annotation vote form
        form_data = {'form-MAX_NUM_FORMS': '1000', 
                     'category_id': node_id, 
                     'form-INITIAL_FORMS': 1, 
                     'form-TOTAL_FORMS': 2,
                     'comment': '',
                     'dataset': '1',
                    }     
        form_data['form-0-visited_sound'] = 'Flase'
        form_data['form-0-annotation_id'] = str(annotation_object_id)
        form_data['form-0-vote'] = '1'
            
        self.client.login(username='username_0', password='123456')
        
        # check the response an that a vote is added in the database
        response = self.client.post(reverse('save-contribute-validate-annotations-per-category'), data=form_data) 
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(Vote.objects.filter(annotation_id=annotation_object_id)), 1)
        
        # check that a second vote is not added
        self.client.post(reverse('save-contribute-validate-annotations-per-category'), data=form_data)
        self.assertEquals(len(Vote.objects.filter(annotation_id=annotation_object_id)), 1)
        
