from django import template
from urllib.parse import quote


register = template.Library()


def calculate_taxonomy_node_stats(
        dataset, node, num_sounds=0, num_annotations=0, num_non_validated_annotations=0, votes_stats=None,
        hierarchy_paths=None, comments=None):

    if votes_stats is not None:
        num_total = votes_stats['num_unsure'] + votes_stats['num_not_present'] \
                    + votes_stats['num_present_not_predominant'] + votes_stats['num_present_and_predominant']
        if num_total:
            votes_stats.update({
                'num_total': num_total,
                'percentage_present_and_predominant': votes_stats['num_present_and_predominant'] * 100 / num_total,
                'percentage_present_not_predominant': votes_stats['num_present_not_predominant'] * 100 / num_total,
                'percentage_not_present': votes_stats['num_not_present'] * 100 / num_total,
                'percentage_unsure': votes_stats['num_unsure'] * 100 / num_total,
                'quality_estimate': (votes_stats['num_present_and_predominant']
                                     + votes_stats['num_present_not_predominant']) * 100 / num_total,
            })
        else:
            votes_stats = {}
    
    # Calculate percentage of validated annotations
    if num_annotations != 0:
        percentage_validated_annotations = (num_annotations - num_non_validated_annotations) * 100.0 / num_annotations
    else:
        percentage_validated_annotations = 0.0

    return {
        'num_sounds': num_sounds,
        'num_annotations': num_annotations,
        'num_non_validated_annotations': num_non_validated_annotations,
        'num_validated_annotations': num_annotations - num_non_validated_annotations,
        'percentage_validated_annotations': percentage_validated_annotations,
        'num_parents': len(node.get('parent_ids', [])),
        'num_children': len(node.get('child_ids', [])),
        'is_abstract': node["abstract"],#'abstract' in node['restrictions'],
        'is_blacklisted': False,#'blacklist' in node['restrictions'],
        'is_omitted': node["omitted"],#'omittedTT' in node['restrictions'],
        'freesound_examples': node['freesound_examples'],
        'url_id': quote(node['node_id'], safe=''),
        'hierarchy_paths': hierarchy_paths if hierarchy_paths is not None else [],
        'votes_stats': votes_stats if votes_stats is not None else {},
        'comments': comments,
        'num_ground_truth': node['nb_ground_truth'],
        'num_verified_annotations': None,
        'num_user_contributions': node['nb_user_contributions'],
    }


@register.simple_tag(takes_context=False)
def taxonomy_node_data(dataset, node_id):
    node = dataset.taxonomy.get_element_at_id(node_id).as_dict()

    num_sounds = dataset.num_sounds_per_taxonomy_node(node_id)
    num_annotations = dataset.num_annotations_per_taxonomy_node(node_id)
    num_non_validated_annotations = dataset.num_non_validated_annotations_per_taxonomy_node(node_id)
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node['node_id'])
    votes_stats = {
        'num_present_and_predominant': dataset.num_votes_with_value(node['node_id'], 1.0),
        'num_present_not_predominant': dataset.num_votes_with_value(node['node_id'], 0.5),
        'num_not_present': dataset.num_votes_with_value(node['node_id'], -1.0),
        'num_unsure': dataset.num_votes_with_value(node['node_id'], 0.0)
    }
    comments = dataset.get_comments_per_taxonomy_node(node['node_id'])

    node = node.copy()  # Duplicate the dict, so update operation below doesn't alter the original dict
    node.update(calculate_taxonomy_node_stats(dataset, node, num_sounds, num_annotations, num_non_validated_annotations,
                                              votes_stats, hierarchy_paths, comments))
    return node


@register.simple_tag(takes_context=False)
def taxonomy_node_minimal_data(dataset, node_id):
    node = dataset.taxonomy.get_element_at_id(node_id).as_dict()
    node = node.copy()  # Duplicate the dict, so update operation below doesn't alter the original dict
    node.update(calculate_taxonomy_node_stats(dataset, node))
    return node


@register.inclusion_tag('datasets/taxonomy_node_small_info.html', takes_context=True)
def display_taxonomy_node_info(context, dataset, node_id, category_link_to='e'):
    user_is_maintainer = dataset.user_is_maintainer(context['request'].user)
    category_link_to = {
        'e': 'dataset-explore-taxonomy-node',
        'cva': 'contribute-validate-annotations-category',
    }[category_link_to]
    node_data = taxonomy_node_data(dataset, node_id)
    return {'dataset': dataset, 'node': node_data, 'category_link_to': category_link_to,
            'user_is_maintainer': user_is_maintainer}


@register.inclusion_tag('datasets/taxonomy_node_mini_info.html')
def display_taxonomy_node_mini_info(dataset, node_id):
    node = dataset.taxonomy.get_element_at_id(node_id).as_dict()
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node['node_id'])
    node['hierarchy_paths'] = hierarchy_paths if hierarchy_paths is not None else []
    return {'dataset': dataset, 'node': node}


@register.simple_tag(takes_context=False)
def sounds_per_taxonomy_node(dataset, node_id, N):
    return dataset.sounds_per_taxonomy_node(node_id)[0:N]


@register.filter()
def fs_embed_small(value):
    embed_code = '<iframe frameborder="0" scrolling="no" src="https://www.freesound.org/embed/sound/iframe/{0}/simple/small/" width="375" height="30"></iframe>'
    return embed_code.format(str(value))


@register.filter()
def fs_embed(value):
    embed_code = '<iframe frameborder="0" scrolling="no" src="https://www.freesound.org/embed/sound/iframe/{0}/simple/medium_no_info/" width="130" height="80"></iframe>'
    return embed_code.format(str(value))

