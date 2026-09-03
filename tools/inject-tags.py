#!/usr/bin/env python3
"""Inject OpenAPI tags for Scalar sidebar grouping, aligned with the official
OpenSearch API reference (https://docs.opensearch.org/latest/api-reference/).

Two-layer resolution, most specific wins:
  1. GROUP_OVERRIDE  -- exact x-operation-group (e.g. cluster.put_component_template
     -> Index, because the official docs file component templates under Index APIs
     even though their operation-group prefix is 'cluster').
  2. PREFIX_MAP      -- x-operation-group prefix (indices -> Index, cat -> CAT, ...).
  3. Path specials   -- UltraWarm / Cold tier by path.

The official Core API groups are: Analyze, CAT, Cluster, Document, Index, Ingest,
List, Nodes, Script, Search, Security, Snapshot, Tasks. Plugin surfaces (ML, SQL,
PPL, Flow Framework, etc.) keep their own groups -- the official docs list them as
"Other APIs" without a single Core bucket.
"""
import json
import sys

# Layer 1: exact operation-group overrides (cross-prefix reclassification to
# match the official docs' information architecture).
GROUP_OVERRIDE = {
    # Component templates: prefix is 'cluster', official docs file under Index APIs.
    'cluster.get_component_template': 'Index',
    'cluster.put_component_template': 'Index',
    'cluster.delete_component_template': 'Index',
    'cluster.exists_component_template': 'Index',
    # Analyze is its own top-level Core group in the official docs.
    'indices.analyze': 'Analyze',
    # validate_query is documented under Search APIs, not Index.
    'indices.validate_query': 'Search',
}

# Layer 2: prefix -> official group.
PREFIX_MAP = {
    # --- Core API groups (official) ---
    'cat': 'CAT',
    'cluster': 'Cluster',
    'dangling_indices': 'Cluster',
    'remote_store': 'Cluster',
    # Index APIs (official folds alias + templates + settings + mappings here)
    'indices': 'Index',
    # Document APIs
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
    'ingestion': 'Document',   # pull-based ingestion (official: Document APIs)
    # Ingest APIs
    'ingest': 'Ingest',
    # List APIs
    'list': 'List',
    # Nodes APIs
    'nodes': 'Nodes',
    # Script APIs
    'put_script': 'Script',
    'get_script': 'Script',
    'delete_script': 'Script',
    'get_script_context': 'Script',
    'get_script_languages': 'Script',
    'scripts_painless_execute': 'Script',
    # Search APIs
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
    # Security APIs
    'security': 'Security',
    # Snapshot APIs
    'snapshot': 'Snapshot',
    # Tasks APIs
    'tasks': 'Tasks',
    # Info / ping (official lists a root Info surface)
    'info': 'Info',
    'ping': 'Info',
    # --- Plugin / "Other APIs" (kept as their own groups) ---
    'search_pipeline': 'Search Pipeline',
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
    'insights': 'Query Insights',
    'wlm': 'Workload Management',
    'ubi': 'User Behavior Insights',
}


def resolve_tag(path, op):
    group = op.get('x-operation-group', '') or ''
    prefix = group.split('.')[0] if group else ''
    # Path specials first (AOS-only tiers)
    if '/_ultrawarm/' in path:
        return 'UltraWarm'
    if '/_cold/' in path:
        return 'Cold Tier'
    # Layer 1: exact override
    if group in GROUP_OVERRIDE:
        return GROUP_OVERRIDE[group]
    # Layer 2: prefix map
    if prefix in PREFIX_MAP:
        return PREFIX_MAP[prefix]
    # Fallback: title-case the prefix
    return prefix.replace('_', ' ').title() if prefix else 'Other'


def inject_tags(input_path, output_path):
    with open(input_path) as f:
        data = json.load(f)

    tag_set = set()
    unmatched = set()

    for path, methods in data.get('paths', {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            tag = resolve_tag(path, op)
            if tag == 'Other' or (
                tag and op.get('x-operation-group', '').split('.')[0] not in PREFIX_MAP
                and op.get('x-operation-group', '') not in GROUP_OVERRIDE
                and '/_ultrawarm/' not in path and '/_cold/' not in path
            ):
                unmatched.add(op.get('x-operation-group', ''))
            op['tags'] = [tag]
            tag_set.add(tag)

    data['tags'] = [{'name': t} for t in sorted(tag_set)]

    with open(output_path, 'w') as f:
        json.dump(data, f)

    print(f'Tags: {len(tag_set)} groups')
    if unmatched:
        print(f'Unmapped operation-groups (fell back to title-case): {sorted(unmatched)}')
    print(f'Written: {output_path}')


if __name__ == '__main__':
    inject_tags(sys.argv[1], sys.argv[2])
