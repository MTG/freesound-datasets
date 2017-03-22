from __future__ import unicode_literals

from django.db import models
from django.db.models import Count
from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.conf import settings
from urllib.parse import quote
import os
import markdown
import datetime
from django.utils import timezone
from django.core.validators import RegexValidator


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

    def get_all_node_ids(self):
        return [e['id'] for e in self.data]

    def get_num_nodes(self):
        return len(self.data)


class Sound(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    freesound_id = models.IntegerField()
    extra_data = JSONField(default={})

    def get_annotations(self, dataset):
        return Annotation.objects.filter(sound_dataset__in=self.sounddataset_set.filter(dataset=dataset))

    def __str__(self):
        return 'Sound {0} (freesound {1})'.format(self.id, self.freesound_id)


class Dataset(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    taxonomy = models.ForeignKey(Taxonomy, null=True, blank=True, on_delete=models.SET_NULL)
    sounds = models.ManyToManyField(Sound, related_name='datasets', through='datasets.SoundDataset')
    maintainers = models.ManyToManyField(User, related_name='maintained_datasets')

    def __str__(self):
        return 'Dataset {0}'.format(self.name)

    @property
    def description_html(self):
        return markdown.markdown(self.description)

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
        if self.num_sounds == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_annotations * 1.0 / self.num_sounds

    @property
    def num_validated_annotations(self):
        # This is the number of annotations that have at least one vote
        return self.annotations.annotate(num_votes=Count('votes')).filter(num_votes__lt=0).count()

    @property
    def percentage_validated_annotations(self):
        if self.num_annotations == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_validated_annotations * 100.0 / self.num_annotations

    @property
    def releases(self):
        return self.datasetrelease_set.all().order_by('-release_date')

    def sounds_per_taxonomy_node(self, node_id):
        return Sound.objects.filter(datasets=self, sounddataset__annotations__value=node_id)

    def num_sounds_per_taxonomy_node(self, node_id):
        return self.sounds_per_taxonomy_node(node_id=node_id).count()

    def annotations_per_taxonomy_node(self, node_id):
        return self.annotations.filter(value=node_id)

    def num_annotations_per_taxonomy_node(self, node_id):
        return self.annotations_per_taxonomy_node(node_id=node_id).count()

    def user_is_maintainer(self, user):
        return user in self.maintainers.all()

    @property
    def last_release_tag(self):
        if not self.releases.all():
            return None
        return self.releases.all().order_by('-release_date')[0].release_tag


class DatasetRelease(models.Model):
    dataset = models.ForeignKey(Dataset)
    num_sounds = models.IntegerField(default=0)
    num_annotations = models.IntegerField(default=0)
    num_validated_annotations = models.IntegerField(default=0)
    # TODO: add total length in seconds
    # TODO: add total size in bytes
    release_date = models.DateTimeField(auto_now_add=True)
    release_tag = models.CharField(max_length=25, validators=[
            RegexValidator(
                regex=r'^[\.a-zA-Z0-9_-]{1,25}$',
                message='Please enter a valid release tag',
            ),
        ])
    is_processed = models.BooleanField(default=False)
    processing_progress = models.IntegerField(default=0)
    processing_last_updated = models.DateTimeField(auto_now_add=True)
    TYPE_CHOICES = (
        ('IN', 'Internal release only'),
        ('PU', 'Public release'),
    )
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='IN')

    @property
    def avg_annotations_per_sound(self):
        if self.num_sounds == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_annotations * 1.0 / self.num_sounds

    @property
    def percentage_validated_annotations(self):
        if self.num_annotations == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_validated_annotations * 100.0 / self.num_annotations

    @property
    def index_file_path(self):
        return os.path.join(settings.DATASET_RELEASE_FILES_FOLDER, '{0}.json'.format(self.id))

    @property
    def last_processing_progress_is_old(self):
        # Check processing_last_updated and if it is older than 5 minutes, that probably means there
        # have been errors with the computation and we can show it on screen
        return self.processing_last_updated < (timezone.now() - datetime.timedelta(minutes=2))


class SoundDataset(models.Model):
    sound = models.ForeignKey(Sound)
    dataset = models.ForeignKey(Dataset)


class Annotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='annotations', null=True, on_delete=models.SET_NULL)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='annotations')
    TYPE_CHOICES = (
        ('MA', 'Manual'),
        ('AU', 'Automatic'),
        ('UK', 'Unknown'),
    )
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='UK')
    algorithm = models.CharField(max_length=200, blank=True, null=True)
    value = models.CharField(max_length=200, db_index=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)

    def __str__(self):
        return 'Annotation for sound {0}'.format(self.sound_dataset.sound.id)


class Vote(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='votes', null=True, on_delete=models.SET_NULL)
    vote = models.IntegerField()
    annotation = models.ForeignKey(Annotation, related_name='votes')

    def __str__(self):
        return 'Vote for annotation {0}'.format(self.annotation.id)
