from django.urls import include, re_path, path
from datasets.views import *
from freesound_datasets.views import discussion


urlpatterns = [
    # this url needs to be in first position to unsure a correct mapping
    re_path(r'^save_contribute_validate_annotations_category/$', save_contribute_validate_annotations_category,
            name='save-contribute-validate-annotations-per-category'),

    #  Dataset
    re_path(r'^(?P<short_name>[^\/]+)/$', dataset, name='dataset'),
    re_path(r'^(?P<short_name>[^\/]+)/explore/$', dataset_explore, name='dataset-explore'),
    re_path(r'^(?P<short_name>[^\/]+)/download-script/$', download_script, name='download-script'),
    re_path(r'^(?P<short_name>[^\/]+)/downloads/$', downloads, name='downloads'),
    re_path(r'^(?P<short_name>[^\/]+)/discussion/', discussion, name='discussion'),
    re_path(r'^(?P<short_name>[^\/]+)/state_table/$', dataset_state_table, name='state-table'),
    re_path(r'^(?P<short_name>[^\/]+)/dataset-sounds/$', dataset_sounds, name='dataset-sounds'),

    # Dataset release
    path('<short_name>/release/<release_tag>/', release_explore, name='dataset-release'),
    re_path(r'^(?P<short_name>[^\/]+)/check_release_progresses/(?P<release_tag>[^\/]+)/$', check_release_progress,
            name='check-release-progresses'),
    re_path(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/change/$', change_release_type,
            name='change-release-type'),
    re_path(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/download/$', download_release,
            name='download-release'),
    re_path(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/delete/$', delete_release,
            name='delete-release'),
    path('<short_name>/release_table/<release_tag>/', dataset_release_table, name='release-table'),
    path('<short_name>/release_table/<release_tag>/taxonomy_table/', release_taxonomy_table,
         name='release-taxonomy-table'),
    path('<short_name>/release/<release_tag>/report_annotation/', report_ground_truth_annotation,
         name='report-ground-truth-annotation'),
    # this url needs to be after the ones above to unsure a correct mapping
    path('<short_name>/release/<release_tag>/<node_id>/', release_taxonomy_node, name='release-taxonomy-node'),

    # Explore, visu tools
    re_path(r'^(?P<short_name>[^\/]+)/taxonomy_table/$', dataset_taxonomy_table, name='taxonomy-table'),
    re_path(r'^(?P<short_name>[^\/]+)/taxonomy_tree/$', dataset_taxonomy_tree, name='taxonomy-tree'),
    re_path(r'^(?P<short_name>[^\/]+)/releases_table/$', dataset_releases_table, name='releases-table'),
    re_path(r'^(?P<short_name>[^\/]+)/explore/(?P<node_id>[^\/]+)/$', taxonomy_node,
            name='dataset-explore-taxonomy-node'),
    re_path(r'^(?P<short_name>[^\/]+)/mini-node-info/(?P<node_id>[^\/]+)/$', get_mini_node_info,
            name='get-mini-node-info'),
    re_path(r'^(?P<short_name>[^\/]+)/node-info/(?P<node_name>[^\/]+)/$', get_node_info, name='get-node-info'),
    re_path(r'^(?P<short_name>[^\/]+)/explore-taxonomy/$', explore_taxonomy, name='explore_taxonomy'),
    re_path(r'^(?P<short_name>[^\/]+)/search_taxonomy_node/$', search_taxonomy_node,
        name='search-taxonomy-node'),

    # Annotate
    re_path(r'^(?P<short_name>[^\/]+)/annotate/$', contribute, name='contribute'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/validate_annotations/$', contribute_validate_annotations,
        name='contribute-validate-annotations'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/validate_annotations/(?P<node_id>[^\/]+)/$',
        contribute_validate_annotations_category, name='contribute-validate-annotations-category'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/validate_annotations_beginner/$',
        contribute_validate_annotations_easy, name='contribute-validate-annotations-category-beginner'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/choose_category/$', choose_category, name='choose_category'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/choose_category_table/$', dataset_taxonomy_table_choose,
        name='dataset_taxonomy_table_choose'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/choose_category_table_search/$', dataset_taxonomy_table_search,
        name='taxonomy-table-search'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/validate_annotations_all/$', contribute_validate_annotations_all,
        name='contribute-validate-annotations-all'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/choose_category_table_search_all/$', dataset_taxonomy_table_search_all,
        name='taxonomy-table-search-all'),   
    re_path(r'^(?P<short_name>[^\/]+)/annotate/curate_sound/(?P<sound_id>[^\/]+)/$', curate_sounds,
        name='expert-curate-sounds'),
    re_path(r'^(?P<short_name>[^\/]+)/annotate/save_expert_votes_curate/(?P<sound_id>[^\/]+)/$', save_expert_votes_curation_task,
        name='save-expert-votes-curate-sounds'),
]
