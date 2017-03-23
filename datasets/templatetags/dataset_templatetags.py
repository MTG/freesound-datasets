from django import template
from urllib.parse import quote


register = template.Library()


@register.simple_tag(takes_context=False)
def taxonomy_node_stats(dataset, node_id, node_n_annotations_n_sounds=None):
    node = dataset.taxonomy.get_element_at_id(node_id)
    # could be an empty list if there are no annotations, explicitly check for None
    if node_n_annotations_n_sounds is None:
        num_sounds = dataset.num_sounds_per_taxonomy_node(node_id)
        num_annotations = dataset.num_annotations_per_taxonomy_node(node_id)
    else:
        try:
            num_sounds = [n_nsounds for n_id, _, n_nsounds in node_n_annotations_n_sounds if n_id == node_id][0]
        except IndexError:
            num_sounds = 0
        try:
            num_annotations = [n_nann for n_id, n_nann, _ in node_n_annotations_n_sounds if n_id == node_id][0]
        except IndexError:
            num_annotations = 0

    # Calculate node hierarchy paths
    hierarchy_paths = dataset.taxonomy.get_hierarchy_paths(node_id)

    return {
        'num_sounds': num_sounds,
        'num_annotations': num_annotations,
        'num_parents': len(node['parents']),
        'num_children': len(node['children']),
        'is_abstract': 'abstract' in node['restrictions'],
        'is_blacklisted': 'blacklist' in node['restrictions'],
        'url_id': quote(node['id'], safe=''),
        'hierarchy_paths': hierarchy_paths,
    }


@register.simple_tag(takes_context=False)
def sounds_per_taxonomy_node(dataset, node_id, N):
    return dataset.sounds_per_taxonomy_node(node_id)[0:N]


@register.filter()
def fs_embed(value):
    embed_code = '<iframe frameborder="0" scrolling="no" src="https://www.freesound.org/embed/sound/iframe/{0}/simple/small/" width="375" height="30"></iframe>'
    return embed_code.format(str(value))
