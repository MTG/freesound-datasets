from django import template
from urllib.parse import quote


register = template.Library()


def calculate_taxonomy_node_stats(dataset, node, num_sounds=0, num_annotations=0, num_non_validated_annotations=0, hierarchy_paths=None):
    
    # Calculate percentage of validated annotations
    if num_annotations != 0:
        percentage_validated_annotations = (num_annotations - num_non_validated_annotations) * 100.0 / num_annotations
    else:
        percentage_validated_annotations = 0.0

    return {
        'num_sounds': num_sounds,
        'num_annotations': num_annotations,
        'num_non_validated_annotations': num_non_validated_annotations,
        'percentage_validated_annotations': percentage_validated_annotations,
        'num_parents': len(node.get('parent_ids', [])),
        'num_children': len(node.get('child_ids', [])),
        'is_abstract': 'abstract' in node['restrictions'],
        'is_blacklisted': 'blacklist' in node['restrictions'],
        'url_id': quote(node['id'], safe=''),
        'hierarchy_paths': hierarchy_paths if hierarchy_paths is not None else [],
    }


@register.simple_tag(takes_context=False)
def taxonomy_node_data(dataset, node_id):
    node = dataset.taxonomy.get_element_at_id(node_id)

    num_sounds = dataset.num_sounds_per_taxonomy_node(node_id)
    num_annotations = dataset.num_annotations_per_taxonomy_node(node_id)
    num_non_validated_annotations = dataset.num_non_validated_annotations_per_taxonomy_node(node_id)
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node['id'])

    node.update(calculate_taxonomy_node_stats(dataset, node, num_sounds, num_annotations, num_non_validated_annotations, hierarchy_paths))
    return node


@register.simple_tag(takes_context=False)
def taxonomy_node_minimal_data(dataset, node_id):
    node = dataset.taxonomy.get_element_at_id(node_id)
    node.update(calculate_taxonomy_node_stats(dataset, node))
    return node


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
