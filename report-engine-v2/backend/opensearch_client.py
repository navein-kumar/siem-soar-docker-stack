"""OpenSearch client - field discovery, query execution, aggregations"""
from opensearchpy import OpenSearch
import config
import urllib3
urllib3.disable_warnings()

def get_client():
    return OpenSearch(
        hosts=[config.OPENSEARCH_URL],
        http_auth=(config.OPENSEARCH_USER, config.OPENSEARCH_PASS),
        use_ssl=True, verify_certs=False, ssl_show_warn=False,
        timeout=30
    )

def discover_fields(index=None):
    """Get all fields from index mapping with types"""
    client = get_client()
    idx = index or config.OPENSEARCH_INDEX
    mapping = client.indices.get_mapping(index=idx)
    
    fields = {}
    for idx_name, idx_data in mapping.items():
        props = idx_data.get("mappings", {}).get("properties", {})
        _extract_fields(props, "", fields)
        break  # just use first index mapping
    
    # Sort and return
    return sorted([
        {"field": f, "type": t, "filterable": t in ["keyword","long","integer","float","double","date","boolean","ip"]}
        for f, t in fields.items()
    ], key=lambda x: x["field"])

def _extract_fields(props, prefix, fields):
    """Recursively extract fields from mapping"""
    for name, spec in props.items():
        full = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        if "properties" in spec:
            _extract_fields(spec["properties"], full, fields)
        else:
            es_type = spec.get("type", "object")
            fields[full] = es_type
            # Also add .keyword for text fields
            if es_type == "text" and "fields" in spec:
                if "keyword" in spec["fields"]:
                    fields[f"{full}.keyword"] = "keyword"

def run_query(query_dsl, index=None, size=0):
    """Execute an OpenSearch query"""
    client = get_client()
    idx = index or config.OPENSEARCH_INDEX
    body = {"size": size, "track_total_hits": True}
    if query_dsl:
        body["query"] = query_dsl
    return client.search(index=idx, body=body)

def run_aggregation(query_dsl, aggs, index=None):
    """Execute query + aggregation"""
    client = get_client()
    idx = index or config.OPENSEARCH_INDEX
    body = {"size": 0, "track_total_hits": True, "aggs": aggs}
    if query_dsl:
        body["query"] = query_dsl
    return client.search(index=idx, body=body)

def get_field_values(field, query_dsl=None, size=20, index=None):
    """Get top values for a field (for autocomplete)"""
    aggs = {"values": {"terms": {"field": field, "size": size}}}
    result = run_aggregation(query_dsl, aggs, index)
    return [b["key"] for b in result["aggregations"]["values"]["buckets"]]
