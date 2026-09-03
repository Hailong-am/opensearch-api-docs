#!/usr/bin/env python3
"""
Preprocess OpenSearch OpenAPI spec:
- Remove deprecated operations
- Inject human-readable summary from x-operation-group
- Append minimum version from x-version-added to description
"""
import json
import sys

def process_spec(spec, inject_version=True):
    removed = 0
    empty_paths = []

    # Build the set of shared component parameters that are marked deprecated,
    # so we can drop operation-level $refs that point at them. master_timeout
    # (superseded by cluster_manager_timeout), legacy local flags, etc. live
    # here and are referenced by many operations.
    comp_params = spec.get('components', {}).get('parameters', {})
    deprecated_refs = {
        f"#/components/parameters/{name}"
        for name, defn in comp_params.items()
        if isinstance(defn, dict) and defn.get('deprecated')
    }
    removed_params = 0

    for path, methods in list(spec.get('paths', {}).items()):
        for method in list(methods.keys()):
            op = methods[method]
            if not isinstance(op, dict):
                continue
            
            # Remove deprecated
            if op.get('deprecated'):
                del methods[method]
                removed += 1
                continue

            # Drop deprecated parameters: inline (param.deprecated) and $refs
            # that resolve to a deprecated shared component parameter.
            params = op.get('parameters')
            if isinstance(params, list):
                kept = []
                for p in params:
                    if isinstance(p, dict):
                        if p.get('deprecated'):
                            removed_params += 1
                            continue
                        if p.get('$ref') in deprecated_refs:
                            removed_params += 1
                            continue
                    kept.append(p)
                if len(kept) != len(params):
                    op['parameters'] = kept
            
            # Inject summary showing the API endpoint path
            if not op.get('summary'):
                op['summary'] = f"{method.upper()} {path}"
            
            # Append version to description. Skipped for serverless (AOSS),
            # which has no engine-version concept -- a "Minimum version" note
            # there is meaningless and misleading.
            if inject_version:
                version = op.get('x-version-added')
                if version:
                    version_note = f"\n\n**Minimum version:** `{version}`"
                    if op.get('description'):
                        op['description'] += version_note
                    else:
                        op['description'] = f"**Minimum version:** `{version}`"
        
        # Remove empty paths
        remaining = [m for m in methods if m in ('get','post','put','delete','head','patch','options','trace')]
        if not remaining:
            empty_paths.append(path)
    
    for p in empty_paths:
        del spec['paths'][p]
    
    return removed, len(empty_paths), removed_params

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    inject_version = '--no-version' not in sys.argv
    if len(args) < 2:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json> [--no-version]")
        sys.exit(1)
    
    with open(args[0]) as f:
        spec = json.load(f)
    
    total_before = sum(1 for p in spec['paths'].values() for m, op in p.items() 
                       if isinstance(op, dict) and 'operationId' in op)
    
    removed, empty, removed_params = process_spec(spec, inject_version=inject_version)
    
    total_after = sum(1 for p in spec['paths'].values() for m, op in p.items() 
                      if isinstance(op, dict) and 'operationId' in op)
    
    with open(args[1], 'w') as f:
        json.dump(spec, f)
    
    print(f"Before: {total_before} operations")
    print(f"Removed: {removed} deprecated ops ({empty} empty paths), {removed_params} deprecated params")
    print(f"After: {total_after} operations{' (version notes suppressed)' if not inject_version else ''}")
    print(f"Written: {args[1]}")
