from __future__ import unicode_literals

import collections
from django.db import models
from django.db.models import Count
from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import os
import markdown
import datetime
import random
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ObjectDoesNotExist
from urllib.parse import quote


class Taxonomy(models.Model):
    data = JSONField()

    @property
    def taxonomy(self):
        return self.data

    def get_parents(self, node_id):
        return self.get_element_at_id(node_id).parents.all()

    def get_propagate_to_parents(self, node_id):
        return self.get_element_at_id(node_id).propagate_to_parents.all()

    def get_children(self, node_id):
        return self.get_element_at_id(node_id).children.all()

    def get_propagate_from_children(self, node_id):
        return self.get_element_at_id(node_id).propagate_from.all()

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
                    for child in get_children(node.node_id, [node] + cur):
                        yield child
        children_list = list(self.get_children(node_id))
        for children in get_children(node_id):
            for child in children:
                if child.node_id not in [n.node_id for n in children_list]:
                    children_list.append(child)

        return children_list

    def get_all_propagate_from_children(self, node_id):
        """
            Returns a list of all the children of the given node id that propagate to the parent
        """
        def get_propagate_from_children(node_id, cur=list()):
            children = self.get_propagate_from_children(node_id)
            if not children:
                yield cur
            else:
                for node in children:
                    for child in get_propagate_from_children(node.node_id, [node] + cur):
                        yield child
        children_list = list(self.get_propagate_from_children(node_id))
        for children in get_propagate_from_children(node_id):
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
                    for parent in get_parents(node.node_id, [node] + cur):
                        yield parent

        parents_list = list(self.get_parents(node_id))
        # this double for loop is for checking if a parent is already in the list
        # in this case, we do not append it to the list
        for parents in get_parents(node_id):
            for parent in parents:
                if parent.node_id not in [n.node_id for n in parents_list]:
                    parents_list.append(parent)

        return parents_list

    def get_all_propagate_to_parents(self, node_id):
        """
            Returns a list of all the children of the given node id
        """
        def get_propagate_to_parents(node_id, cur=list()):
            parents = self.get_propagate_to_parents(node_id)
            if not parents:
                yield cur
            else:
                for node in parents:
                    for parent in get_propagate_to_parents(node.node_id, [node] + cur):
                        yield parent

        parents_list = list(self.get_propagate_to_parents(node_id))
        # this double for loop is for checking if a parent is already in the list
        # in this case, we do not append it to the list
        for parents in get_propagate_to_parents(node_id):
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
    deleted_in_freesound = models.BooleanField(default=False, db_index=True)
    extra_data = JSONField(default={})

    app_label = 'datasets'
    model_name = 'sound'

    def get_candidate_annotations(self, dataset):
        return CandidateAnnotation.objects.filter(sound_dataset__in=self.sounddataset_set.filter(dataset=dataset))

    def __str__(self):
        return 'Sound {0} (freesound {1})'.format(self.id, self.freesound_id)


validator_list_examples = RegexValidator('^([0-9]+(?:,[0-9]+)*)*$', message='Enter a list of comma separated Freesound IDs.')

class TaxonomyNode(models.Model):
    node_id = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    citation_uri = models.CharField(max_length=100, null=True, blank=True)
    abstract = models.BooleanField(default=False)
    omitted = models.BooleanField(default=False)
    freesound_examples = models.ManyToManyField(Sound, related_name='taxonomy_node')
    freesound_examples_verification = models.ManyToManyField(Sound, related_name='taxonomy_node_verification')
    positive_verification_examples_activated = models.BooleanField(default=True)
    freesound_false_examples = models.ManyToManyField(Sound)
    negative_verification_examples_activated = models.BooleanField(default=True)
    taxonomy = models.ForeignKey(Taxonomy, null=True, blank=True, on_delete=models.SET_NULL)
    parents = models.ManyToManyField('self', symmetrical=False, related_name='children')
    propagate_to_parents = models.ManyToManyField('self', symmetrical=False, related_name='propagate_from')
    faq = models.TextField(blank=True)
    nb_ground_truth = models.IntegerField(default=0)
    # for easy admin example change:
    list_freesound_examples = models.CharField(max_length=100, null=True, blank=True, validators=[validator_list_examples])
    list_freesound_examples_verification = models.CharField(max_length=100, null=True, blank=True, validators=[validator_list_examples])
    beginner_task = models.BooleanField(default=False)
    advanced_task = models.BooleanField(default=False, db_index=True)

    app_label = 'datasets'
    model_name = 'taxonomynode'

    # override save for sync examples and list_examples (easy admin editing of FS examples)
    def save(self, *args, **kwargs):
        old = TaxonomyNode.objects.filter(pk=getattr(self, 'pk', None)).first()
        if old:
            if old.list_freesound_examples != self.list_freesound_examples:
                self.freesound_examples.clear()
                for fsid in self.list_freesound_examples.split(','):
                    try:
                        sound = Sound.objects.get(freesound_id=fsid)
                        self.freesound_examples.add(sound)
                    except ObjectDoesNotExist:
                        pass
            if old.list_freesound_examples_verification != self.list_freesound_examples_verification:
                self.freesound_examples_verification.clear()
                for fsid in self.list_freesound_examples_verification.split(','):
                    try:
                        sound = Sound.objects.get(freesound_id=fsid)
                        self.freesound_examples_verification.add(sound)
                    except ObjectDoesNotExist:
                        pass
            if old.freesound_examples != self.freesound_examples:
                self.list_freesound_examples = ','.join(
                    [str(fsid) for fsid in list(self.freesound_examples.values_list('freesound_id', flat=True))])
            if old.freesound_examples_verification != self.freesound_examples_verification:
                self.list_freesound_examples_verification = ','.join(
                    [str(fsid) for fsid in list(self.freesound_examples_verification.values_list('freesound_id', flat=True))])
        super(TaxonomyNode, self).save(*args, **kwargs)

    def as_dict(self):
        parents = self.get_parents()
        return {"name": self.name,
                "node_id": self.node_id,
                "id": self.id,
                "description": self.description,
                "citation_uri": self.citation_uri,
                "abstract": self.abstract,
                "omitted": self.omitted,
                "freesound_examples": list(self.valid_examples),
                "parent_ids": [parent.node_id for parent in parents],
                "child_ids": [child.node_id for child in self.get_children()],
                "sibling_ids": [sibling.node_id for sibling in self.get_siblings(parents)],
                "nb_ground_truth": self.num_ground_truth_annotations,
                "nb_propagated_ground_truth": self.num_propagated_ground_truth_annotations,
                "nb_user_contributions": self.num_user_contributions,
                "nb_verified_annotations": self.num_verified_annotations,
                "faq": self.faq,
                "url_id": self.url_id}

    @property
    def url_id(self):
        # Used to return url for node ids
        return quote(self.node_id, safe='')

    @property
    def name_with_parent(self):
        """ Used for printing the category name (with parent) in the choose table"""
        parents = self.parents.all()
        num_parents = parents.count()
        if num_parents == 0:  # no parent
            return self.name
        elif num_parents < 2:  # one parent
            return '{} > {}'.format(parents[0].name, self.name)
        else:  # several parents
            return ' (many parents) > {}'.format(self.name)

    @property
    def self_and_children_omitted(self):
        """ Returns True if the node and all its children are omitted """
        all_children = self.taxonomy.get_all_children(self.node_id)
        return all(omitted for omitted in [child.omitted for child in all_children] + [self.omitted])

    @property
    def self_and_children_advanced_task(self):
        """ Returns False if the node and all its children have advanced_task False """
        all_children = self.taxonomy.get_all_children(self.node_id)
        return any(advanced_task for advanced_task in [child.advanced_task for child in all_children]
                   + [self.advanced_task])

    @property
    def num_user_contributions(self):
        return Vote.objects.filter(candidate_annotation__taxonomy_node=self).count()

    @property
    def num_verified_annotations(self):
        return CandidateAnnotation.objects.filter(taxonomy_node=self).exclude(ground_truth__isnull=True).count()

    @property
    def num_ground_truth_annotations(self):
        return self.ground_truth_annotations.count()

    @property
    def num_propagated_ground_truth_annotations(self):
        return self.ground_truth_annotations.filter(from_propagation=True).count()

    def get_parents(self):
        return self.parents.all()

    def get_children(self):
        return self.children.all()

    def get_siblings(self, parents=None):
        if not parents:
            parents = self.get_parents()
        return TaxonomyNode.objects.filter(parents__in=parents).exclude(node_id=self.node_id).distinct()

    @property
    def siblings(self):
        return self.get_siblings()

    @property
    def valid_examples(self):
        return self.freesound_examples.filter(deleted_in_freesound=False).values_list('freesound_id', flat=True)

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.node_id)


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
    def candidate_annotations(self):
        return CandidateAnnotation.objects.filter(sound_dataset__dataset=self)

    @property
    def ground_truth_annotations(self):
        return GroundTruthAnnotation.objects.all()

    @property
    def num_sounds(self):
        return self.sounds.all().count()

    @property
    def num_annotations(self):
        return self.candidate_annotations.count()

    @property
    def avg_annotations_per_sound(self):
        if self.num_sounds == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_annotations * 1.0 / self.num_sounds

    @property
    def num_validated_annotations(self):
        # This is the number of annotations that have at least one vote
        return self.candidate_annotations.annotate(num_votes=Count('votes')).filter(num_votes__gt=0).count()

    @property
    def percentage_validated_annotations(self):
        if self.num_annotations == 0:
            return 0  # Avoid potential division by 0 error
        return self.num_validated_annotations * 100.0 / self.num_annotations

    @property
    def num_ground_truth_annotations(self):
        # This is the number of annotations that have ground truth state PP (1) or PNP (0.5)
        return self.ground_truth_annotations.count()

    @property
    def num_verified_annotations(self):
        return self.candidate_annotations.exclude(ground_truth__isnull=True).count()

    @property
    def percentage_verified_annotations(self):
        if self.num_annotations == 0:
            return 0
        return self.num_verified_annotations * 100.0 / self.num_annotations

    @property
    def num_user_contributions(self):
        return Vote.objects.filter(candidate_annotation__sound_dataset__dataset=self).count()

    @property
    def releases(self):
        return self.datasetrelease_set.all().order_by('-release_date')

    def sounds_per_taxonomy_node(self, node_id):
        return Sound.objects.filter(datasets=self, sounddataset__candidate_annotations__taxonomy_node__node_id=node_id)

    def num_sounds_per_taxonomy_node(self, node_id):
        return self.sounds_per_taxonomy_node(node_id=node_id).count()

    def annotations_per_taxonomy_node(self, node_id):
        return self.candidate_annotations.filter(taxonomy_node__node_id=node_id)

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
        return self.candidate_annotations.filter(taxonomy_node__node_id=node_id).filter(ground_truth=None)

    def get_categories(self):
        return self.taxonomy.taxonomynode_set

    def get_categories_to_validate(self, user):
        """
        Returns a query set with the TaxonomyNode that can be validated by a user
        Quite slow, should not be use often
        """
        taxonomy_node_pk = self.sounds.filter(sounddataset__candidate_annotations__ground_truth=None)\
            .exclude(sounddataset__candidate_annotations__votes__created_by=user)\
            .filter(taxonomy_node=None, taxonomy_node_verification=None)\
            .values_list('sounddataset__candidate_annotations__taxonomy_node', flat=True)
        return self.taxonomy.taxonomynode_set.filter(pk__in=set(taxonomy_node_pk))

    def user_can_annotate(self, node_id, user):
        """
        Returns True if the user still have some annotation to validate for the category of id node_id
        Returns False if the user has no no more annotation to validate
        """
        node = self.taxonomy.get_element_at_id(node_id)

        sound_examples_verification = node.freesound_examples_verification.all()
        sound_examples = node.freesound_examples.all()

        annotation_examples_verification_ids = self.candidate_annotations.filter(
            sound_dataset__sound__in=sound_examples_verification,
            taxonomy_node=node).values_list('id', flat=True)
        annotation_examples_ids = self.candidate_annotations.filter(
            sound_dataset__sound__in=sound_examples,
            taxonomy_node=node).values_list('id', flat=True)

        num_eligible_annotations = self.non_ground_truth_annotations_per_taxonomy_node(node_id)\
            .exclude(votes__created_by=user)\
            .exclude(id__in=annotation_examples_verification_ids)\
            .exclude(id__in=annotation_examples_ids)\
            .filter(sound_dataset__sound__deleted_in_freesound=False).count()

        if num_eligible_annotations == 0:
            return False
        else:
            return True

    def num_votes_with_value(self, node_id, vote_value):
        return Vote.objects.filter(
            candidate_annotation__sound_dataset__dataset=self, candidate_annotation__taxonomy_node__node_id=node_id, vote=vote_value).count()

    def num_votes_with_value_after_date(self, node_id, vote_value, reference_date):
        return Vote.objects.filter(
            candidate_annotation__sound_dataset__dataset=self, candidate_annotation__taxonomy_node__node_id=node_id,
            vote=vote_value, created_at__gt=reference_date).count()

    def get_comments_per_taxonomy_node(self, node_id):
        return CategoryComment.objects.filter(dataset=self, category_id=node_id)

    def user_is_maintainer(self, user):
        return user in self.maintainers.all()

    @property
    def last_release_tag(self):
        if not self.releases.all():
            return None
        return self.releases.all().order_by('-release_date')[0].release_tag

    @property
    def random_fs_sound_id(self):
        last = self.sounds.count() - 1
        random_index = random.randint(0, last-1)
        sounds = self.sounds.all()[random_index]
        return sounds.freesound_id

    def get_random_taxonomy_node_with_examples(self, num_nodes=10):
        nodes = self.taxonomy.taxonomynode_set.annotate(nb_examples=Count('freesound_examples'))\
            .filter(nb_examples__gte=2)
        random_idx = random.sample(range(len(nodes)), min(num_nodes, len(nodes)))
        return [nodes[idx] for idx in random_idx]


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


class CandidateAnnotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    TYPE_CHOICES = (
        ('MA', 'Manual'),
        ('AU', 'Automatic'),
        ('UK', 'Unknown'),
    )
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='UK')
    algorithm = models.CharField(max_length=200, blank=True, null=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    ground_truth = models.FloatField(null=True, blank=True, default=None)
    created_by = models.ForeignKey(User, related_name='candidate_annotations', null=True, on_delete=models.SET_NULL)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='candidate_annotations')
    taxonomy_node = models.ForeignKey(TaxonomyNode, blank=True, null=True, related_name='candidate_annotations')

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
        vote_values = [v.vote for v in self.votes.all() if v.test is not 'FA']
        # all the test cases are considered valid except the Failed one
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

    @property
    def freesound_id(self):
        return self.sound_dataset.sound.freesound_id

    def num_vote_value(self, value):
        vote_values = [v.vote for v in self.votes.all() if v.test is not 'FA']
        return vote_values.count(value)

    @property
    def num_PP(self):
        return self.num_vote_value(1)

    @property
    def num_PNP(self):
        return self.num_vote_value(0.5)

    @property
    def num_U(self):
        return self.num_vote_value(0)

    @property
    def num_NP(self):
        return self.num_vote_value(-1)


class GroundTruthAnnotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    ground_truth = models.FloatField(null=True, blank=True, default=None)
    created_by = models.ForeignKey(User, related_name='ground_truth_annotations', null=True, on_delete=models.SET_NULL)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='ground_truth_annotations')
    taxonomy_node = models.ForeignKey(TaxonomyNode, blank=True, null=True, related_name='ground_truth_annotations')
    from_candidate_annotation = models.ForeignKey(CandidateAnnotation, blank=True, null=True)
    from_propagation = models.BooleanField(default=False)

    @property
    def value(self):
        return self.taxonomy_node.node_id

    def __str__(self):
        return 'Annotation for sound {0}'.format(self.sound_dataset.sound.id)

    def propagate_annotation(self):
        propagate_to_parents = self.taxonomy_node.taxonomy.get_all_propagate_to_parents(self.taxonomy_node.node_id)
        for parent in propagate_to_parents:
            GroundTruthAnnotation.objects.get_or_create(start_time=self.start_time,
                                                        end_time=self.end_time,
                                                        ground_truth=self.ground_truth,
                                                        created_by=self.created_by,
                                                        sound_dataset=self.sound_dataset,
                                                        taxonomy_node=parent,
                                                        from_candidate_annotation=self.from_candidate_annotation,
                                                        from_propagation=True)


# choices for quality control test used in Vote and User Profile
TEST_CHOICES = (
    ('UN', 'Unknown'),  # Test was not implemented when user contributed
    ('AP', 'All Passed'),  # All test successfully passed
    ('PP', 'Positive Passed'),  # Only positive examples test activated and passed
    ('NP', 'Negative Passed'),  # Only negative examples test activated and passed
    ('NA', 'None Activated'),  # No examples test activated
    ('FA', 'Failed'),  # One of the test failed, or not tested yet
)


class Vote(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='votes', null=True, on_delete=models.SET_NULL)
    vote = models.FloatField()
    candidate_annotation = models.ForeignKey(CandidateAnnotation, related_name='votes', null=True)
    visited_sound = models.NullBooleanField(null=True, blank=True, default=None)
    # 'visited_sound' is to store whether the user needed to open the sound in Freesound to perform this vote
    test = models.CharField(max_length=2, choices=TEST_CHOICES, default='UN')  # Store test result
    from_test_page = models.NullBooleanField(null=True, blank=True, default=None)  # Store if votes are from a test page
    TASK_TYPES = (
        ('BE', 'Beginner'),
        ('AD', 'Advanced')
    )
    from_task = models.CharField(max_length=2, choices=TASK_TYPES, default='AD')  # store from which validation task

    def __str__(self):
        return 'Vote for annotation {0}'.format(self.candidate_annotation.id)

    def save(self, request=False, *args, **kwargs):
        super(Vote, self).save(*args, **kwargs)
        # here calculate ground truth for vote.annotation
        candidate_annotation = self.candidate_annotation
        ground_truth_state = candidate_annotation.ground_truth_state
        if ground_truth_state in (0.5, 1.0):
            candidate_annotation.ground_truth = ground_truth_state
            candidate_annotation.save()
            ground_truth_annotation, created = GroundTruthAnnotation.objects.get_or_create(
                start_time=candidate_annotation.start_time,
                end_time=candidate_annotation.end_time,
                ground_truth=candidate_annotation.ground_truth,
                created_by=candidate_annotation.created_by,
                sound_dataset=candidate_annotation.sound_dataset,
                taxonomy_node=candidate_annotation.taxonomy_node,
                from_candidate_annotation=candidate_annotation,
                from_propagation=False)
            if created:
                ground_truth_annotation.propagate_annotation()


class CategoryComment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='comments', null=True, on_delete=models.SET_NULL)
    dataset = models.ForeignKey(Dataset)
    comment = models.TextField(blank=True)
    category_id = models.CharField(max_length=200)
    # NOTE: currently categories are not stored as db objects, therefore we store a reference to the category (node) id
    # as used in other parts of the application. At some point categories should be stored as db objects and this
    # should refer to the db object id.


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    test = models.CharField(max_length=2, choices=TEST_CHOICES, default='UN')  # Store test result
    countdown_trustable = models.IntegerField(default=0)  # count for make the user pass the test again
    last_category_annotated = models.ForeignKey(TaxonomyNode, null=True, blank=True, default=None)
    # this store the last category the user contributed to

    def refresh_countdown(self):
        self.countdown_trustable = 3
        self.save()

    @property
    def contributed_recently(self):
        return self.contributed_before(3)

    @property
    def contributed_two_weeks_ago(self):
        return self.contributed_before(14)

    def contributed_before(self, days_ago):
        try:
            last_contribution_date = self.user.votes.order_by('-created_at')[0].created_at
            past_date = timezone.now() - datetime.timedelta(days=days_ago)
            return last_contribution_date > past_date
        except IndexError:
            return False

    @property
    def is_fsd_maintainer(self):
        dataset = Dataset.objects.get(short_name='fsd')
        return dataset.user_is_maintainer(self.user)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
