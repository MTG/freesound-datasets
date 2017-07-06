from __future__ import unicode_literals

import collections
from django.db import models
from django.db.models import Count
from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.conf import settings
import os
import markdown
import datetime
from django.utils import timezone
from django.core.validators import RegexValidator
from urllib.parse import quote


class Taxonomy(models.Model):
    data = JSONField()

    @property
    def taxonomy(self):
        return self.data

    def get_parents(self, node_id):
        return self.get_element_at_id(node_id).parents.all()

    def get_children(self, node_id):
        return self.get_element_at_id(node_id).children.all()

    def get_element_at_id(self, node_id):
        return self.taxonomynode_set.get(node_id=node_id)

    def get_all_nodes(self):
        return self.taxonomynode_set.all().order_by('name')

    def get_all_node_ids(self):
        return [node.node_id for node in self.taxonomynode_set.all()]

    def get_num_nodes(self):
        return self.taxonomynode_set.count()

    def get_hierarchy_paths(self, node_id):

        def paths(node_id, cur=list()):
            parents = self.get_parents(node_id)
            if not parents:
                yield cur
            else:
                for node in parents:
                    for path in paths(node.node_id, [node.node_id] + cur):
                        yield path

        hierarchy_paths = list()
        for path in paths(node_id):
            # Add root and current category to path
            hierarchy_paths.append(path + [self.get_element_at_id(node_id).node_id])

        return hierarchy_paths

    def get_all_children(self, node_id):
        """
            Returns a list of all the children of the given node id
        """
        def get_children(node_id, cur=list()):
            children = self.get_children(node_id)
            if not children:
                yield cur
            else:
                for node in children:
                    for child in get_children(node.node_id, [node]):
                        yield child
        children_list = list(self.get_children(node_id))
        for children in get_children(node_id):
            for child in children:
                if child.node_id not in [n.node_id for n in children_list]:
                    children_list.append(child)

        return children_list

    def get_all_parents(self, node_id):
        """
            Returns a list of all the children of the given node id
        """
        def get_parents(node_id, cur=list()):
            parents = self.get_parents(node_id)
            if not parents:
                yield cur
            else:
                for node in parents:
                    for parent in get_parents(node.node_id, [node]):
                        yield parent

        parents_list = list(self.get_parents(node_id))
        # this double for loop is for checking if a parent is already in the list
        # in this case, we do not append it to the list
        for parents in get_parents(node_id):
            for parent in parents:
                if parent.node_id not in [n.node_id for n in parents_list]:
                    parents_list.append(parent)

        return parents_list

    def get_nodes_at_level(self, level):
        """
            Returns a list of all the nodes at a given level of the taxonomy
        """
        def flat_list(l):
            return [item for sublist in l for item in sublist]

        if level == 0:
            return self.taxonomynode_set.filter(parents=None)
        else:
            parent_node_ids = self.get_nodes_at_level(level-1)
            return flat_list([parent.children.all() for parent in parent_node_ids])

    def get_taxonomy_as_tree(self):
        """
            Returns a dictionary for the tree visualization
        """
        keys = [("name", "name"), ("mark", "restrictions")]
        def get_all_children(node_id):
            # recursive function for adding children in dict 
            children = self.get_children(node_id)
            children_names = []
            for child in children:
                child_name = {"name":child.name, "mark":[]}
                if child.abstract:
                    child_name["mark"].append("abstract")
                if child.omitted:
                    child_name["mark"].append("omittedTT")
                child_name["children"] = get_all_children(child.node_id)
                children_names.append(child_name)
            if children_names: 
                return children_names
        
        higher_categories = self.taxonomynode_set.filter(parents=None)
        output_dict = {"name":"Ontology", "children":[]}
        for node in higher_categories:
            dict_level = {"name":node.name, "mark":[]}
            if node.abstract:
                dict_level["mark"].append("abstract")
            if node.omitted:
                dict_level["mark"].append("omittedTT")
            dict_level["children"] = get_all_children(node.node_id)
            output_dict["children"].append(dict_level)
            
        return output_dict


class Sound(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    freesound_id = models.IntegerField(db_index=True)
    extra_data = JSONField(default={})

    def get_annotations(self, dataset):
        return Annotation.objects.filter(sound_dataset__in=self.sounddataset_set.filter(dataset=dataset))

    def __str__(self):
        return 'Sound {0} (freesound {1})'.format(self.id, self.freesound_id)


class TaxonomyNode(models.Model):
    node_id = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    citation_uri = models.CharField(max_length=100)
    abstract = models.BooleanField(default=False)
    omitted = models.BooleanField(default=False)
    freesound_examples = models.ManyToManyField(Sound, related_name='taxonomy_node')
    taxonomy = models.ForeignKey(Taxonomy, null=True, blank=True, on_delete=models.SET_NULL)
    parents = models.ManyToManyField('self', symmetrical=False, related_name='children')
    nb_ground_truth = models.IntegerField(default=0)
    
    def as_dict(self):
        return {"name": self.name,
                "node_id": self.node_id,
                "id": self.id,
                "description": self.description,
                "citation_uri": self.citation_uri,
                "abstract": self.abstract,
                "omitted": self.omitted,
                "freesound_examples": [example.freesound_id for example in self.freesound_examples.all()],
                "parent_ids": [parent.node_id for parent in self.parents.all()],
                "child_ids": [child.node_id for child in self.children.all()],
                "nb_ground_truth": self.nb_ground_truth}

    @property
    def url_id(self):
        # Used to return url for node ids
        return quote(self.node_id, safe='')

    
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
        return self.annotations.annotate(num_votes=Count('votes')).filter(num_votes__gt=0).count()

    @property
    def percentage_validated_annotations(self):
        if self.num_annotations == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_validated_annotations * 100.0 / self.num_annotations

    @property
    def releases(self):
        return self.datasetrelease_set.all().order_by('-release_date')

    def sounds_per_taxonomy_node(self, node_id):
        return Sound.objects.filter(datasets=self, sounddataset__annotations__taxonomy_node__node_id=node_id)

    def num_sounds_per_taxonomy_node(self, node_id):
        return self.sounds_per_taxonomy_node(node_id=node_id).count()

    def annotations_per_taxonomy_node(self, node_id):
        return self.annotations.filter(taxonomy_node__node_id=node_id)

    def num_annotations_per_taxonomy_node(self, node_id):
        return self.annotations_per_taxonomy_node(node_id=node_id).count()

    def non_validated_annotations_per_taxonomy_node(self, node_id):
        return self.annotations_per_taxonomy_node(node_id).annotate(num_votes=Count('votes')).filter(num_votes__lte=0)

    def num_non_validated_annotations_per_taxonomy_node(self, node_id):
        return self.non_validated_annotations_per_taxonomy_node(node_id).count()

    def non_ground_truth_annotations_per_taxonomy_node(self, node_id):
        """
        Returns annotations that have no vote agreement
        """
        all_annotations = self.annotations_per_taxonomy_node(node_id).annotate(num_votes=Count('votes'))
        # this commented code should work but is super slow... With ground_truth as a field it will be fast!
        #non_ground_truth_pk = [annotation.pk for annotation in all_annotations if annotation.ground_truth is False]
        ground_truth_pk = []
        for vote_value in [-1, 0, 0.5, 1]:
            ground_truth_pk += [a.pk for a in all_annotations.filter(votes__vote=vote_value).
                                annotate(num_votes=Count('votes')).filter(num_votes__gt=1)]
        return all_annotations.exclude(pk__in=ground_truth_pk).order_by('-num_votes')
        #return all_annotations.filter(pk__in=non_ground_truth_pk)

    def get_categories_to_validate(self, user):
        """
        Returns a query set with the TaxonomyNode that can be validated by a user
        Quite slow, should not be use often
        """
        nodes = self.taxonomy.taxonomynode_set.all()
        nodes_to_keep = [node.node_id for node in nodes if self.user_can_annotate(node.node_id, user)]
        return nodes.filter(node_id__in=nodes_to_keep)

    def user_can_annotate(self, node_id, user):
        """
        Returns True if the user still have some annotation to validate for the category of id node_id
        Returns False if the user has no no more annotation to validate
        """
        if self.non_ground_truth_annotations_per_taxonomy_node(node_id).exclude(votes__created_by=user).count() < 1:
            return False
        else:
            return True

    def num_votes_with_value(self, node_id, vote_value):
        return Vote.objects.filter(
            annotation__sound_dataset__dataset=self, annotation__taxonomy_node__node_id=node_id, vote=vote_value).count()

    def get_comments_per_taxonomy_node(self, node_id):
        return CategoryComment.objects.filter(dataset=self, category_id=node_id)

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
    num_nodes = models.IntegerField(default=0)
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
    taxonomy_node = models.ForeignKey(TaxonomyNode, blank=True, null=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    ground_truth = models.FloatField(null=True, blank=True, default=None)

    def __str__(self):
        return 'Annotation for sound {0}'.format(self.sound_dataset.sound.id)
    
    @property
    def value(self):
        return self.taxonomy_node.node_id

    @property
    def ground_truth_state(self):
        """
        Returns the ground truth vote value of the annotation
        Returns None if there is no ground truth value
        """
        vote_values = [v.vote for v in self.votes.all()]
        if vote_values.count(1) > 1:
            return 1
        if vote_values.count(0.5) > 1:
            return 0.5
        if vote_values.count(0) > 1:
            return 0
        if vote_values.count(-1) > 1:
            return -1
        else:
            return None


class Vote(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='votes', null=True, on_delete=models.SET_NULL)
    vote = models.FloatField()
    annotation = models.ForeignKey(Annotation, related_name='votes')
    visited_sound = models.NullBooleanField(null=True, blank=True, default=None)
    # 'visited_sound' is to store whether the user needed to open the sound in Freesound to perform this vote

    def __str__(self):
        return 'Vote for annotation {0}'.format(self.annotation.id)

    def save(self, request=False, *args, **kwargs):
        models.Model.save(self, *args, **kwargs)
        # here calculate ground truth for vote.annotation
        ground_truth_state = self.annotation.ground_truth_state
        if ground_truth_state:
            self.annotation.ground_truth = ground_truth_state
            self.annotation.save()


class CategoryComment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='comments', null=True, on_delete=models.SET_NULL)
    dataset = models.ForeignKey(Dataset)
    comment = models.TextField(blank=True)
    category_id = models.CharField(max_length=200)
    # NOTE: currently categories are not stored as db objects, therefore we store a reference to the category (node) id
    # as used in other parts of the application. At some point categories should be stored as db objects and this
    # should refer to the db object id.

