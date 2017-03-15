from __future__ import unicode_literals

from django.db import models
from django.db.models import Count
from django.contrib.postgres.fields import JSONField
from urllib.parse import quote


class Taxonomy(models.Model):
    data = JSONField()

    def preprocess_taxonomy(self):
        # This should only be done once, now it is implemented as a sort oh hack, called after url patterns...
        processed_data = list()
        for node in self.data:
            new_node = {key: value for key, value in node.items()}
            children = self.get_children(node['id'])
            parents = self.get_parents(node['id'])
            new_node.update({
                'url_id': quote(node['id'], safe=''),
                'children': children,
                'parents': parents,
            })
            processed_data.append(new_node)
        self.data = processed_data
        self.save()

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
                return e

    def get_parents(self, ontology_id):
        parents = []
        for e in self.data:
            if ontology_id in e['child_ids']:
                parents.append(self.get_element_at_id(e['id']))
        return parents

    def get_children(self, ontology_id):
        for e in self.data:
            if e['id'] == ontology_id:
                return [self.get_element_at_id(child_id) for child_id in e['child_ids']]
        return None

    def get_element_at_id(self, ontology_id):
        for e in self.data:
            if e['id'] == ontology_id:
                return e
        return None

    def get_all_nodes(self):
        names_ids_list = [(e['id'], e['name']) for e in self.data]  # Quote id as it contains slashes
        sorted_names_ids_list = sorted(names_ids_list, key=lambda x: x[1])  # Sort by name
        return [self.get_element_at_id(node_id) for node_id, _ in sorted_names_ids_list]


class Sound(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    freesound_id = models.IntegerField()
    extra_data = JSONField(default={})

    def __str__(self):
        return 'Sound {0} (freesound {1})'.format(self.id, self.freesound_id)


class Dataset(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    taxonomy = models.ForeignKey(Taxonomy, null=True, blank=True, on_delete=models.SET_NULL)
    sounds = models.ManyToManyField(Sound, related_name='datasets', through='datasets.SoundDataset')

    def __str__(self):
        return 'Dataset {0}'.format(self.name)

    @property
    def annotations(self):
        return Annotation.objects.filter(sound_dataset__dataset=self)

    @property
    def num_sounds(self):
        return self.sounds.all().count()

    @property
    def num_annotations(self):
        return self.annotations.count()

    @property
    def avg_annotations_per_sound(self):
        return self.num_annotations * 1.0 / self.num_sounds

    @property
    def num_validated_annotations(self):
        return len([item for item in self.annotations.annotate(num_votes=Count('votes')) if item.num_votes > 0])

    @property
    def percentage_validated_annotations(self):
        return self.num_validated_annotations * 100.0 / self.num_annotations

    def sounds_per_taxonomy_node(self, node_id):
        # TODO: implement this properly
        return self.annotations.filter(value=node_id)#.values_list('sound_dataset__sound', flat=True)

    def num_sounds_per_taxonomy_node(self, node_id):
        return self.sounds_per_taxonomy_node(node_id=node_id).count()


class SoundDataset(models.Model):
    sound = models.ForeignKey(Sound)
    dataset = models.ForeignKey(Dataset)


class Annotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='annotations')
    TYPE_CHOICES = (
        ('MA', 'Manual'),
        ('AU', 'Automatic'),
        ('UK', 'Unknown'),
    )
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='UK')
    # TODO: add created_by property (user, can be null)
    algorithm = models.CharField(max_length=200, blank=True, null=True)
    value = models.CharField(max_length=200)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)

    def __str__(self):
        return 'Annotation for sound {0}'.format(self.sound_dataset.sound.id)


class Vote(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    # TODO: add created_by property (user)
    vote = models.IntegerField()
    annotation = models.ForeignKey(Annotation, related_name='votes')

    def __str__(self):
        return 'Vote for annotation {0}'.format(self.annotation.id)
