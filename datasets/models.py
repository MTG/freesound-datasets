from __future__ import unicode_literals

import collections
from django.db import models, transaction
from django.db.models import Count, Q
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
from functools import reduce


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

    def get_element_from_name(self, name):
        return self.taxonomynode_set.get(name=name)

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
        node = self.taxonomynode_set.get(node_id=node_id)
        return self.taxonomynode_set.filter(Q(parents=node) |
                                            Q(parents__parents=node) |
                                            Q(parents__parents__parents=node) |
                                            Q(parents__parents__parents__parents=node) |
                                            Q(parents__parents__parents__parents__parents=node) |
                                            Q(parents__parents__parents__parents__parents__parents=node) |
                                            Q(parents__parents__parents__parents__parents__parents__parents=node)
                                            ).distinct()

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
        node = self.taxonomynode_set.get(node_id=node_id)
        return self.taxonomynode_set.filter(Q(children=node) |
                                            Q(children__children=node) |
                                            Q(children__children__children=node) |
                                            Q(children__children__children__children=node) |
                                            Q(children__children__children__children__children=node) |
                                            Q(children__children__children__children__children__children=node) |
                                            Q(children__children__children__children__children__children__children=node)
                                            ).distinct()

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
            return list(self.taxonomynode_set.filter(parents=None))
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
                child_name = {"name": child.name, "mark": [], "node_id": child.node_id}
                if child.abstract:
                    child_name["mark"].append("abstract")
                if child.omitted:
                    child_name["mark"].append("omittedTT")
                child_name["children"] = get_all_children(child.node_id)
                children_names.append(child_name)
            if children_names: 
                return children_names
        
        higher_categories = self.taxonomynode_set.filter(parents=None)
        output_dict = {"name": "Ontology", "children": []}
        for node in higher_categories:
            dict_level = {"name": node.name, "mark": [], "node_id": node.node_id}
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

    def get_ground_truth_annotations(self, dataset):
        return GroundTruthAnnotation.objects.filter(sound_dataset__in=self.sounddataset_set.filter(dataset=dataset))

    def get_image_url(self, img_type, size):
        img_types = ['spectrogram', 'waveform']
        sizes = ['M', 'L']
        if img_type not in img_types:
            raise ValueError
        if size not in sizes:
            raise ValueError
        url_parts = self.extra_data['previews'].split('previews')
        prefix = url_parts[0].replace('https:', '').replace('http:', '')   # remove 'https:' or 'http:'
        freesound_id_pref = url_parts[1].split('/')[1]
        user_id = url_parts[1].split('_')[-1].split('-')[0]
        params = {
            'prefix': prefix,
            'freesound_id_pref': freesound_id_pref,
            'freesound_id': self.freesound_id,
            'user_id': user_id,
            'size': size
        }
        if img_type == 'spectrogram':
            img_url = self.build_spectrogram_url(params)
        elif img_type == 'waveform':
            img_url = self.build_waveform_url(params)
        return img_url

    def build_spectrogram_url(self, params):
        prefix = params['prefix']
        freesound_id_pref = params['freesound_id_pref']
        freesound_id = params['freesound_id']
        user_id = params['user_id']
        size = params['size']
        spec_url = "{0}displays/{1}/{2}_{3}_spec_{4}.jpg".format(prefix,
                                                                freesound_id_pref,
                                                                freesound_id,
                                                                user_id,
                                                                size)
        return spec_url

    def build_waveform_url(self, params):
        prefix = params['prefix']
        freesound_id_pref = params['freesound_id_pref']
        freesound_id = params['freesound_id']
        user_id = params['user_id']
        size = params['size']
        wave_url = "{0}displays/{1}/{2}_{3}_wave_{4}.png".format(prefix,
                                                                freesound_id_pref,
                                                                freesound_id,
                                                                user_id,
                                                                size)
        return wave_url

    def get_loudness_normalizing_ratio(self, descriptor, target_loudness_value, max_gain_ratio):
        try:
            if descriptor == 'ebur128':
                loudness_value = self.extra_data.get('analysis', dict()).get('ebur128', target_loudness_value)
                normalizing_ratio_db = float(target_loudness_value - loudness_value)
            elif descriptor == 'replayGain':
                normalizing_ratio_db = self.extra_data.get('analysis', dict()).get('replayGain', 0)
            else:
                raise ValueError
        except (AttributeError, TypeError):
            normalizing_ratio_db = 0

        normalizing_ratio = 10 ** (normalizing_ratio_db / 20.0)

        return normalizing_ratio if normalizing_ratio <= max_gain_ratio else max_gain_ratio

    def __str__(self):
        return 'Sound {0} (freesound {1})'.format(self.id, self.freesound_id)


validator_list_examples = RegexValidator('^([0-9]+(?:,[0-9]+)*)*$', message='Enter a list of comma separated Freesound IDs.')

class TaxonomyNode(models.Model):
    node_id = models.CharField(max_length=20)
    name = models.CharField(max_length=100, db_index=True)
    description = models.CharField(max_length=500, db_index=True)
    citation_uri = models.CharField(max_length=100, null=True, blank=True)
    abstract = models.BooleanField(default=False)
    omitted = models.BooleanField(default=False, db_index=True)
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
                if self.list_freesound_examples:
                    for fsid in self.list_freesound_examples.split(','):
                        if fsid != '':
                            try:
                                sound = Sound.objects.get(freesound_id=fsid)
                                self.freesound_examples.add(sound)
                            except ObjectDoesNotExist:
                                pass
            if old.list_freesound_examples_verification != self.list_freesound_examples_verification:
                self.freesound_examples_verification.clear()
                if self.list_freesound_examples_verification:
                    for fsid in self.list_freesound_examples_verification.split(','):
                        if fsid != '':
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
        return not all_children.filter(omitted=False).exists() and self.omitted

    @property
    def self_and_children_advanced_task(self):
        """ Returns False if the node and all its children have advanced_task False """
        all_children = self.taxonomy.get_all_children(self.node_id)
        return all_children.filter(advanced_task=True).exists() or self.advanced_task

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

    @property
    def hierarchy_paths(self):
        return self.taxonomy.get_hierarchy_paths(self.node_id)

    def quality_estimate(self):
        votes = list(Vote.objects.filter(candidate_annotation__taxonomy_node=self)\
                                 .exclude(test='FA')\
                                 .values_list('vote', flat=True))
        num_PP = votes.count(1.0)
        num_PNP = votes.count(0.5)
        num_NP = votes.count(-1)
        num_U = votes.count(0)
        num_votes = num_PP + num_PNP + num_NP + num_U
        try:
            quality_estimate = float(num_PP + num_PNP) / num_votes
        except ZeroDivisionError:
            quality_estimate = 0

        return {
            'quality_estimate': quality_estimate,
            'num_PP': num_PP,
            'num_PNP': num_PNP,
            'num_NP': num_NP,
            'num_U': num_U,
            'num_votes': num_votes,
            'num_sounds': self.candidate_annotations.count()
        }

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
    def num_sounds_with_candidate(self):
        return self.sounds.filter(sounddataset__candidate_annotations__isnull=False).distinct().count()

    @property
    def num_non_omitted_nodes(self):
        return self.taxonomy.taxonomynode_set.filter(omitted=False).count()

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
            .filter(taxonomy_node=None,
                    taxonomy_node_verification=None,
                    deleted_in_freesound=False,
                    sounddataset__candidate_annotations__priority_score__gt=0)\
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

        num_eligible_annotations = self.non_ground_truth_annotations_per_taxonomy_node(node_id) \
            .exclude(id__in=Vote.objects.filter(candidate_annotation__taxonomy_node=node,
                                                created_by=user,
                                                test__in=('UN', 'AP', 'PP', 'NA', 'NP'))
                     .values('candidate_annotation_id')) \
            .exclude(id__in=annotation_examples_verification_ids) \
            .exclude(id__in=annotation_examples_ids) \
            .exclude(priority_score=0) \
            .filter(sound_dataset__sound__deleted_in_freesound=False).count()

        if num_eligible_annotations == 0:
            return False
        else:
            return True

    def num_votes_with_value(self, node_id, vote_value):
        return Vote.objects.filter(
            candidate_annotation__sound_dataset__dataset=self,
            candidate_annotation__taxonomy_node__node_id=node_id,
            vote=vote_value)\
            .exclude(test='FA')\
            .count()

    def num_votes_with_value_after_date(self, node_id, vote_value, reference_date):
        return Vote.objects.filter(
            candidate_annotation__sound_dataset__dataset=self,
            candidate_annotation__taxonomy_node__node_id=node_id,
            vote=vote_value,
            created_at__gt=reference_date)\
            .exclude(test='FA')\
            .count()

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

    @property
    def num_categories_reached_goal(self):
        num_nodes_reached_goal = self.taxonomy.taxonomynode_set.filter(omitted=False, nb_ground_truth__gte=100).count()
        nodes_pk = self.sounds.filter(sounddataset__candidate_annotations__ground_truth=None,
                                      taxonomy_node=None,
                                      taxonomy_node_verification=None,
                                      deleted_in_freesound=False,
                                      sounddataset__candidate_annotations__priority_score__gt=0)\
            .values_list('sounddataset__candidate_annotations__taxonomy_node', flat=True)
        num_nodes_finished_verifying = self.taxonomy.taxonomynode_set.filter(omitted=False, nb_ground_truth__lt=100)\
            .exclude(pk__in=set(nodes_pk)).count()
        return num_nodes_reached_goal + num_nodes_finished_verifying

    def retrieve_sound_by_tags(self, positive_tags, negative_tags, preproc_positive=True, preproc_negative=False):
        r = self.sounds.all()
        if positive_tags:
            if preproc_positive:
                r = r.filter(reduce(lambda x, y: x | y,
                                    [reduce(lambda w, z: w & z, [Q(extra_data__stemmed_tags__contains=item)
                                                                 if type(items) == list
                                                                 else Q(extra_data__stemmed_tags__contains=items)
                                                                 for item in items])
                                     for items in positive_tags]))
            else:
                r = r.filter(reduce(lambda x, y: x | y,
                                    [reduce(lambda w, z: w & z, [Q(extra_data__tags__contains=item)
                                                                 if type(items) == list
                                                                 else Q(extra_data__tags__contains=items)
                                                                 for item in items])
                                     for items in positive_tags]))

        if negative_tags:
            if preproc_negative:
                for negative_tag in negative_tags:
                    r = r.exclude(extra_data__stemmed_tags__contains=negative_tag)
            else:
                for negative_tag in negative_tags:
                    r = r.exclude(extra_data__tags__contains=negative_tag)
        return r

    def quality_estimate_mapping(self, results, node_id):
        votes = Vote.objects.filter(candidate_annotation__sound_dataset__dataset=self,
                                    candidate_annotation__taxonomy_node__node_id=node_id,
                                    candidate_annotation__sound_dataset__sound__in=results.values_list('id', flat=True))\
                            .exclude(test='FA')
        votes_values = list(votes.values_list('vote', flat=True))
        num_votes = len(votes_values)

        num_PP = votes_values.count(1.0)
        num_PNP = votes_values.count(0.5)
        num_NP = votes_values.count(-1)
        num_U = votes_values.count(0)

        tags_in_NP = [tag
                      for v in votes if v.vote == -1
                      for tag in v.candidate_annotation.sound_dataset.sound.extra_data['tags']]
        tags_with_count = sorted(list(set([(i, tags_in_NP.count(i)) for i in tags_in_NP])),
                                 key=lambda x: x[1],
                                 reverse=True)

        try:
            quality_estimate = float(num_PP + num_PNP) / num_votes
        except ZeroDivisionError:
            quality_estimate = 0

        result = {
            'quality_estimate': quality_estimate,
            'num_PP': num_PP,
            'num_PNP': num_PNP,
            'num_NP': num_NP,
            'num_U': num_U,
            'num_votes': num_votes,
            'tags_in_NP': tags_with_count
        }

        return result


class DatasetRelease(models.Model):
    dataset = models.ForeignKey(Dataset, null=True, blank=True, on_delete=models.SET_NULL)
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
    sound = models.ForeignKey(Sound, null=True, blank=True, on_delete=models.SET_NULL)
    dataset = models.ForeignKey(Dataset, null=True, blank=True, on_delete=models.SET_NULL)


class CandidateAnnotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    TYPE_CHOICES = (
        ('MA', 'Manual'),
        ('AU', 'Automatic'),
        ('UK', 'Unknown'),
    )
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='UK')
    algorithm = models.TextField(max_length=1000, blank=True, null=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    ground_truth = models.FloatField(null=True, blank=True, default=None)
    created_by = models.ForeignKey(User, related_name='candidate_annotations', null=True, on_delete=models.SET_NULL)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='candidate_annotations',
                                      null=True, blank=True, on_delete=models.SET_NULL)
    taxonomy_node = models.ForeignKey(TaxonomyNode, related_name='candidate_annotations',
                                      null=True, blank=True, on_delete=models.SET_NULL)
    priority_score = models.IntegerField(default=1)

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
        # all the test cases are considered valid except the Failed one
        vote_values_non_expert = [v.vote for v in self.votes.all() if v.test != 'FA' and not v.from_expert]
        vote_values_expert = [v.vote for v in self.votes.all() if v.test != 'FA' and v.from_expert]

        if vote_values_expert:
            if vote_values_expert.count(1) > 0:
                return 1
            if vote_values_expert.count(0.5) > 0:
                return 0.5
            if vote_values_expert.count(0) > 0:
                return 0
            if vote_values_expert.count(-1) > 0:
                return -1
        else:
            if vote_values_non_expert.count(1) > 1:
                return 1
            if vote_values_non_expert.count(0.5) > 1:
                return 0.5
            if vote_values_non_expert.count(0) > 1:
                return 0
            if vote_values_non_expert.count(-1) > 1:
                return -1
            else:
                return None

    @property
    def freesound_id(self):
        return self.sound_dataset.sound.freesound_id

    def num_vote_value(self, value):
        vote_values = [v.vote for v in self.votes.all() if v.test != 'FA']
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

    def return_priority_score(self):
        sound_duration = self.sound_dataset.sound.extra_data['duration']
        num_present_votes = self.num_present_votes if hasattr(self, 'num_present_votes') \
                            else self.votes.exclude(test='FA').filter(vote__in=('1', '0.5')).count()
        if not 0.3 <= sound_duration <= 30:
            return num_present_votes
        else:
            duration_score = 3 if sound_duration <= 10 else 2 if sound_duration <= 20 else 1
            num_gt_same_sound = self.sound_dataset.ground_truth_annotations.filter(from_propagation=False).count()
            return 1000 * num_present_votes \
                 +  100 * duration_score \
                 +        num_gt_same_sound

    def update_priority_score(self):
        self.priority_score = self.return_priority_score()
        self.save()


class GroundTruthAnnotation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    end_time = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    ground_truth = models.FloatField(null=True, blank=True, default=None)
    created_by = models.ForeignKey(User, related_name='ground_truth_annotations', null=True, on_delete=models.SET_NULL)
    sound_dataset = models.ForeignKey(SoundDataset, related_name='ground_truth_annotations',
                                      null=True, blank=True, on_delete=models.SET_NULL)
    taxonomy_node = models.ForeignKey(TaxonomyNode, related_name='ground_truth_annotations',
                                      null=True, blank=True, on_delete=models.SET_NULL)
    # keep all the candidate annotations that generated this annotation (from progation or not)
    from_candidate_annotations = models.ManyToManyField(CandidateAnnotation,
                                                        related_name='generated_ground_truth_annotations')
    from_propagation = models.BooleanField(default=False)  # true when this annotation was generated only from propagation

    class Meta:
        unique_together = ('taxonomy_node', 'sound_dataset',)

    @property
    def value(self):
        return self.taxonomy_node.node_id

    def __str__(self):
        return 'Annotation for sound {0}'.format(self.sound_dataset.sound.id)

    def propagate_annotation(self, from_expert=False):
        propagate_to_parents = self.taxonomy_node.taxonomy.get_all_propagate_to_parents(self.taxonomy_node.node_id)
        for parent in propagate_to_parents:
            gt_annotation, created = GroundTruthAnnotation.objects.get_or_create(
                    sound_dataset=self.sound_dataset,
                    taxonomy_node=parent,
                    defaults={
                        'start_time': self.start_time,
                        'end_time': self.end_time,
                        'ground_truth': self.ground_truth,
                        'created_by': self.created_by,
                        'from_propagation': True,
                    }
            )
            gt_annotation.from_candidate_annotations.add(*self.from_candidate_annotations.all())

            if not created:
                if from_expert:  # a ground truth could be modified when voted by an expert
                    # take the maximum presence value from all the candidate annotations
                    gt_annotation.ground_truth = max(gt_annotation.from_candidate_annotations.values_list(
                        'ground_truth', flat=True))
                    gt_annotation.save()

    def unpropagate_annotation(self, origin_candidate_annotation):
        propagate_to_parents = self.taxonomy_node.taxonomy.get_all_propagate_to_parents(self.taxonomy_node.node_id)

        propagated_annotations = GroundTruthAnnotation.objects.filter(sound_dataset=self.sound_dataset,
                                                                      taxonomy_node__in=propagate_to_parents)

        # remove the candidate annotation from the which we unpropagate
        for annotation in propagated_annotations:
            annotation.from_candidate_annotations.remove(origin_candidate_annotation)

        # delete the ground truth annotations that have no candidate from the which it originally propagated
        # update num ground truth annotations for the parent taxonomy node
        ground_truth_annotations_to_delete = GroundTruthAnnotation.objects.filter(
            sound_dataset=self.sound_dataset,
            taxonomy_node__in=propagate_to_parents,
            from_candidate_annotations__isnull=True,
        ).select_related('taxonomy_node')

        if ground_truth_annotations_to_delete:
            taxonomy_nodes_to_update = [gt.taxonomy_node for gt in ground_truth_annotations_to_delete]
            ground_truth_annotations_to_delete.delete()
            for node in taxonomy_nodes_to_update:
                node.nb_ground_truth = node.num_ground_truth_annotations
                node.save()

    # Update number of ground truth annotations per taxonomy node each time a ground truth annotations is generated
    # Update priority score of candidate annotations associated to the same sound (only for non propagated gt annotations)
    def save(self, *args, **kwargs):
        super(GroundTruthAnnotation, self).save(*args, **kwargs)
        self.taxonomy_node.nb_ground_truth = self.taxonomy_node.num_ground_truth_annotations
        self.taxonomy_node.save()
        if not self.from_propagation:
            for candidate_annotation in self.sound_dataset.candidate_annotations.all():
                candidate_annotation.update_priority_score()


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
    candidate_annotation = models.ForeignKey(CandidateAnnotation, related_name='votes',
                                             null=True, on_delete=models.CASCADE)
    visited_sound = models.NullBooleanField(null=True, blank=True, default=None)
    # 'visited_sound' is to store whether the user needed to open the sound in Freesound to perform this vote
    test = models.CharField(max_length=2, choices=TEST_CHOICES, default='UN')  # Store test result
    from_test_page = models.NullBooleanField(null=True, blank=True, default=None)  # Store if votes are from a test page
    TASK_TYPES = (
        ('BE', 'Beginner'),
        ('AD', 'Advanced')
    )
    from_task = models.CharField(max_length=2, choices=TASK_TYPES, default='AD')  # store from which validation task
    from_expert = models.BooleanField(default=False)

    def __str__(self):
        return 'Vote for annotation {0}'.format(self.candidate_annotation.id)

    def save(self, request=False, *args, **kwargs):
        super(Vote, self).save(*args, **kwargs)
        # here calculate ground truth for vote.annotation
        # create ground truth annotations, update priority score when needed
        candidate_annotation = self.candidate_annotation
        initial_ground_truth = candidate_annotation.ground_truth

        # maximum one annotation exists with unique pair (taxonomy_node, sound_dataset,)
        existing_annotation = GroundTruthAnnotation.objects.filter(
            sound_dataset=candidate_annotation.sound_dataset,
            taxonomy_node=candidate_annotation.taxonomy_node,
        ).first()

        ground_truth_state = candidate_annotation.ground_truth_state

        if initial_ground_truth != ground_truth_state:

            if ground_truth_state in (-1.0, 0):     # annotation reach NP or U state
                candidate_annotation.ground_truth = ground_truth_state
                candidate_annotation.save()

                # a ground truth can be deleted if an expert votes it U or NP
                # in this case we unpropagate the annotation and remove it
                if existing_annotation:
                    if self.from_expert:
                        associated_sound_dataset = existing_annotation.sound_dataset
                        existing_annotation.unpropagate_annotation(candidate_annotation)
                        existing_annotation.delete()
                        for candidate_annotation in associated_sound_dataset.candidate_annotations.all():
                            candidate_annotation.update_priority_score()

            elif ground_truth_state in (0.5, 1.0):  # annotation reach PP or PNP state
                candidate_annotation.ground_truth = ground_truth_state
                candidate_annotation.save()

                if existing_annotation:  # a ground truth could be modified when voted by an expert
                    if self.from_expert:
                        existing_annotation.ground_truth = candidate_annotation.ground_truth
                        existing_annotation.save()
                        existing_annotation.propagate_annotation(from_expert=True)

                else:
                    # normal agreement reached -> create a ground truth annotation
                    ground_truth_annotation = GroundTruthAnnotation.objects.create(
                        start_time=candidate_annotation.start_time,
                        end_time=candidate_annotation.end_time,
                        ground_truth=candidate_annotation.ground_truth,
                        created_by=candidate_annotation.created_by,
                        sound_dataset=candidate_annotation.sound_dataset,
                        taxonomy_node=candidate_annotation.taxonomy_node,
                        from_propagation=False)
                    ground_truth_annotation.from_candidate_annotations.add(candidate_annotation)
                    ground_truth_annotation.propagate_annotation()

        else:  # no change on the ground truth state, update the priority score which depends on his number of votes
            candidate_annotation.update_priority_score()


class CategoryComment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='comments', null=True, on_delete=models.SET_NULL)
    dataset = models.ForeignKey(Dataset, null=True, on_delete=models.SET_NULL)
    comment = models.TextField(blank=True)
    category_id = models.CharField(max_length=200)
    # NOTE: this should refer to the db object id.


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    test = models.CharField(max_length=2, choices=TEST_CHOICES, default='UN')  # Store test result
    countdown_trustable = models.IntegerField(default=0)  # count for make the user pass the test again
    last_category_annotated = models.ForeignKey(TaxonomyNode,
                                                null=True, blank=True, default=None, on_delete=models.SET_NULL)
    # this store the last category the user contributed to

    def refresh_countdown(self):
        self.countdown_trustable = 3
        self.save()

    @property
    def last_date_annotated(self):
        try:
            return self.user.votes.order_by('-created_at')[0].created_at
        except:
            return None

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
