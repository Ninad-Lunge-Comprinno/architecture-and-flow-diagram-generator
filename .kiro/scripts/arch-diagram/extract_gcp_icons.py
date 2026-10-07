#!/usr/bin/env python3
"""
Extract GCP icon SVG base64 data from draw.io sidebar source.
"""

import re
import urllib.request
import sys

# Services we need to extract
SERVICES = [
    'bigquery',
    'cloud_pubsub',  # Pub/Sub
    'cloud_dataflow',  # Dataflow
    'cloud_dataproc',  # Dataproc
    'cloud_scheduler',  # Cloud Scheduler
    'cloud_workflows',  # Workflows
    'artifact_registry',  # Artifact Registry
    'cloud_monitoring',  # Cloud Monitoring
    'cloud_build',  # Cloud Build
    'cloud_logging',  # Cloud Logging
    'cloud_run',  # Cloud Run
    'cloud_storage',  # Cloud Storage
    'cloud_iam',  # Cloud IAM / Identity
    'user',  # Generic user/person
]

def fetch_sidebar_source(url):
    """Fetch the sidebar JavaScript source."""
    with urllib.request.urlopen(url) as response:
        return response.read().decode('utf-8')

def extract_icon_base64(js_content, service_name_pattern):
    """
    Extract base64 icon data for a service.
    Look for patterns like:
    var icon = 'PHN2ZyB4bWxu...==;';
    this.addGCP2UserProductCardSet('BigQuery', ...
    """
    # Pattern to match icon assignment followed by addGCP2UserProductCardSet or addEntry
    # The icon is a base64 string between single quotes
    pattern = rf"icon\s*=\s*'([A-Za-z0-9+/=]+);';\s*this\.add[^(]*\([^,]*{service_name_pattern}"
    
    match = re.search(pattern, js_content, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    
    # Try alternative pattern for inline definitions
    pattern2 = rf"image=data:image/svg\+xml,([A-Za-z0-9+/=%]+)[;'\"].*?{service_name_pattern}"
    match2 = re.search(pattern2, js_content, re.IGNORECASE)
    if match2:
        return match2.group(1)
    
    return None

def main():
    # URLs to check
    urls = [
        'https://raw.githubusercontent.com/jgraph/drawio/dev/src/main/webapp/js/diagramly/sidebar/Sidebar-GCP2.js',
        'https://raw.githubusercontent.com/jgraph/drawio/dev/src/main/webapp/js/diagramly/sidebar/Sidebar-GCP.js',
    ]
    
    results = {}
    
    for url in urls:
        print(f"Fetching {url}...", file=sys.stderr)
        try:
            js_content = fetch_sidebar_source(url)
            print(f"Fetched {len(js_content)} bytes", file=sys.stderr)
            
            # Service name mappings for pattern matching
            service_patterns = {
                'bigquery': r"BigQuery|bigquery|big\s+query",
                'cloud_pubsub': r"Pub/Sub|pubsub|pub\s+sub",
                'cloud_dataflow': r"Dataflow|dataflow",
                'cloud_dataproc': r"Dataproc|dataproc",
                'cloud_scheduler': r"Cloud\s+Scheduler|scheduler",
                'cloud_workflows': r"Workflows|workflows",
                'artifact_registry': r"Artifact\s+Registry|artifact",
                'cloud_monitoring': r"Cloud\s+Monitoring|monitoring",
                'cloud_build': r"Cloud\s+Build|build",
                'cloud_logging': r"Cloud\s+Logging|logging",
                'cloud_run': r"Cloud\s+Run|cloud\s+run",
                'cloud_storage': r"Cloud\s+Storage|storage",
                'cloud_iam': r"Cloud\s+IAM|Identity|IAM",
                'user': r"User\s+1|User\s+Device|user",
            }
            
            for service_key, pattern in service_patterns.items():
                if service_key not in results:
                    base64_data = extract_icon_base64(js_content, pattern)
                    if base64_data:
                        results[service_key] = base64_data
                        print(f"✓ Found {service_key}", file=sys.stderr)
        except Exception as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
    
    # Output results as Python dict
    print("\n# Extracted GCP icon base64 data")
    print("_GCP_ICON_SVG = {")
    for service in SERVICES:
        if service in results:
            print(f"    '{service}': '{results[service]}',")
        else:
            print(f"    # '{service}': None,  # NOT FOUND")
    print("}")
    
    # Summary
    print(f"\n# Found {len(results)}/{len(SERVICES)} icons", file=sys.stderr)
    missing = [s for s in SERVICES if s not in results]
    if missing:
        print(f"# Missing: {', '.join(missing)}", file=sys.stderr)

if __name__ == '__main__':
    main()
