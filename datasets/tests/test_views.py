from django.test import Client, TestCase
from datasets.models import *
from datasets.views import *
from datasets.forms import *
from datasets.management.commands.generate_fake_data import create_sounds, create_users, create_annotations

class ContributeTest(TestCase):
    fixtures = ['datasets/fixtures/initial.json']
    
    def setUp(self):
        create_sounds('fsd', 12)
        create_users(1)
        create_annotations('fsd', 24)
        
    def test_save_contribute_validate_annotations_category(self):
        # get a node id with at least one annotation
        node_id = Annotation.objects.filter(sound_dataset__gt=1)[0].value
        annotations = dataset.non_validated_annotations_per_taxonomy_node(node_id)
        all_annotation_object_ids = annotations.values_list('id', flat=True)
        nb_annotations = min(len(all_annotation_object_ids), 12)
        
        form_data = {'form-MAX_NUM_FORMS': ['1000'], 
                     'category_id': [node_id], 
                     'form-INITIAL_FORMS': [nb_annotations], 
                     'csrfmiddlewaretoken': ['qcPfVgmrpSKmUcU30cA48OHybUJfbEtQ5YZPsjx5azuPoyr7HkbuPQaAyPfJzyWc'],
                     'form-TOTAL_FORMS': [nb_annotations + 1],
                    }
        for i in range(nb_annotations):      
            form_data['form-{0}-visited_sound'.format(i)] = ['True', 'False'][i%2]
            form_data['form-{0}-annotation_id'.format(i)] = all_annotation_object_ids[i]
            form_data['form-{0}-vote'] = [1, -1, 1][i%3]
            
        response = self.client.post(reverse('save-contribute-validate-annotations-per-category', form_data))
        response2 = self.client.post(reverse('save-contribute-validate-annotations-per-category', form_data))
        
        
        
#        form_data = {'form-10-visited_sound': ['False'], 'form-11-vote': ['0'], 'form-1-vote': ['0'], 'form-6-vote': ['0'], 'form-2-vote': ['0'], 'form-0-vote': ['0'], 'form-5-visited_sound': ['False'], 'form-1-visited_sound': ['False'], 'form-7-vote': ['0'], 'form-7-visited_sound': ['False'], 'form-0-visited_sound': ['False'], 'comment': [''], 'form-4-vote': ['0'], 'form-10-vote': ['0'], 'form-4-annotation_id': ['214827'], 'form-7-annotation_id': ['313069'], 'form-5-vote': ['0'], 'form-11-annotation_id': ['648349'], 'form-9-annotation_id': ['412470'], 'csrfmiddlewaretoken': ['qcPfVgmrpSKmUcU30cA48OHybUJfbEtQ5YZPsjx5azuPoyr7HkbuPQaAyPfJzyWc'], 'form-6-visited_sound': ['False'], 'form-8-visited_sound': ['False'], 'dataset': ['1'], 'form-0-annotation_id': ['1700'], 'form-TOTAL_FORMS': ['13'], 'form-2-annotation_id': ['80457'], 'form-1-annotation_id': ['3370'], 'form-4-visited_sound': ['False'], 'form-5-annotation_id': ['247442'], 'form-8-vote': ['0'], 'form-MAX_NUM_FORMS': ['1000'], 'form-11-visited_sound': ['False'], 'form-9-visited_sound': ['False'], 'form-9-vote': ['0'], 'form-6-annotation_id': ['287498'], 'form-2-visited_sound': ['False'], 'form-3-annotation_id': ['175177'], 'form-3-visited_sound': ['False'], 'form-8-annotation_id': ['359251'], 'form-10-annotation_id': ['574778'], 'form-INITIAL_FORMS': ['12'], 'form-MIN_NUM_FORMS': ['0'], 'form-3-vote': ['0'], 'category_id': ['/m/0k5j']} 
        
        #response = c.post(reverse('save-contribute-validate-annotations-per-category'), form)
        