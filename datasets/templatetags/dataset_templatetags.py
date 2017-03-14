from django import template


register = template.Library()


@register.simple_tag(takes_context=False)
def taxonomy_node_stats(dataset, node_id):
    return {
        'num_sounds': dataset.num_sounds_per_taxonomy_node(node_id),
        'num_parents': len(dataset.taxonomy.get_element_at_id(node_id)['parents']),
        'num_children': len(dataset.taxonomy.get_element_at_id(node_id)['children']),
    }
