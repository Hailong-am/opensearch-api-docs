#!/usr/bin/env python3
"""Inject OpenAPI tags from x-operation-group for Scalar sidebar grouping."""
import json
import sys

# Map x-operation-group prefix -> display tag
# Groups with < 4 ops get folded into a parent category
TAG_MAP = {
    # Core
    'indices': 'Indices',
    'cluster': 'Cluster',
    'cat': 'Cat',
    'nodes': 'Nodes',
    'tasks': 'Tasks',
    'ingest': 'Ingest',
    'snapshot': 'Snapshot',
    'dangling_indices': 'Cluster',
    'remote_store': 'Cluster',
    # Document
    'index': 'Document',
    'get': 'Document',
    'exists': 'Document',
    'delete': 'Document',
    'update': 'Document',
    'create': 'Document',
    'bulk': 'Document',
    'bulk_stream': 'Document',
    'mget': 'Document',
    'reindex': 'Document',
    'delete_by_query': 'Document',
    'update_by_query': 'Document',
    'delete_by_query_rethrottle': 'Document',
    'update_by_query_rethrottle': 'Document',
    'reindex_rethrottle': 'Document',
    'get_source': 'Document',
    'exists_source': 'Document',
    'termvectors': 'Document',
    'mtermvectors': 'Document',
    # Search
    'search': 'Search',
    'msearch': 'Search',
    'count': 'Search',
    'field_caps': 'Search',
    'rank_eval': 'Search',
    'search_shards': 'Search',
    'search_template': 'Search',
    'msearch_template': 'Search',
    'render_search_template': 'Search',
    'explain': 'Search',
    'scroll': 'Search',
    'clear_scroll': 'Search',
    'create_pit': 'Search',
    'delete_pit': 'Search',
    'delete_all_pits': 'Search',
    'get_all_pits': 'Search',
    'search_pipeline': 'Search Pipeline',
    # Script
    'put_script': 'Script',
    'get_script': 'Script',
    'delete_script': 'Script',
    'get_script_context': 'Script',
    'get_script_languages': 'Script',
    'scripts_painless_execute': 'Script',
    # Plugins
    'security': 'Security',
    'ml': 'ML Commons',
    'ltr': 'Learning to Rank',
    'knn': 'k-NN',
    'neural': 'Neural Search',
    'sql': 'SQL',
    'ppl': 'PPL',
    'ism': 'Index State Management',
    'sm': 'Snapshot Management',
    'rollups': 'Index State Management',
    'transforms': 'Index State Management',
    'flow_framework': 'Flow Framework',
    'search_relevance': 'Search Relevance',
    'notifications': 'Notifications',
    'observability': 'Observability',
    'asynchronous_search': 'Asynchronous Search',
    'replication': 'Cross-Cluster Replication',
    'geospatial': 'Geospatial',
    'security_analytics': 'Security Analytics',
    'query': 'Query Insights',
    'wlm': 'Workload Management',
    'ingestion': 'Ingestion',
    'insights': 'Query Insights',
    'ubi': 'User Behavior Insights',
    'list': 'List',
    # Info
    'info': 'Info',
    'ping': 'Info',
}

def inject_tags(input_path, output_path):
    with open(input_path) as f:
        data = json.load(f)

    tag_set = set()
    unmatched = set()

    for path, methods in data.get('paths', {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            group = op.get('x-operation-group', '')
            prefix = group.split('.')[0] if group else ''

            # Special: ultrawarm/cold from path
            if '/_ultrawarm/' in path:
                tag = 'UltraWarm'
            elif '/_cold/' in path:
                tag = 'Cold Tier'
            elif prefix in TAG_MAP:
                tag = TAG_MAP[prefix]
            else:
                tag = prefix.replace('_', ' ').title() if prefix else 'Other'
                unmatched.add(prefix)

            op['tags'] = [tag]
            tag_set.add(tag)

    # Add tag definitions sorted
    data['tags'] = [{'name': t} for t in sorted(tag_set)]

    with open(output_path, 'w') as f:
        json.dump(data, f)

    print(f'Tags: {len(tag_set)} groups')
    if unmatched:
        print(f'Unmapped prefixes: {sorted(unmatched)}')
    print(f'Written: {output_path}')

if __name__ == '__main__':
    inject_tags(sys.argv[1], sys.argv[2])
