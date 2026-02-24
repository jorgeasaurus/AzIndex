#!/usr/bin/env python3
"""
parse_docs.py — Parse azure-docs-powershell to generate AzIndex data files.

Usage:
    python scripts/parse_docs.py <path-to-azure-docs-powershell>

Output:
    public/data/manifest.json
    public/data/descriptions.json
    public/data/modules/Az.<Module>.json
"""

import os
import re
import json
import sys
from pathlib import Path

# ── Category mapping ──────────────────────────────────────────────────────────
CATEGORY_MAP = [
    ("Accounts", "Authentication"),
    ("Compute", "Compute"),
    ("Network", "Networking"),
    ("Storage", "Storage"),
    ("Sql", "Database"),
    ("CosmosDb", "Database"),
    ("Redis", "Database"),
    ("Monitor", "Monitoring"),
    ("Advisor", "Governance"),
    ("Policy", "Governance"),
    ("Security", "Security"),
    ("KeyVault", "Security"),
    ("Identity", "Identity"),
    ("Aks", "Containers"),
    ("ContainerInstance", "Containers"),
    ("ContainerRegistry", "Containers"),
    ("App", "App Services"),
    ("Websites", "App Services"),
    ("Functions", "App Services"),
    ("Logic", "Integration"),
    ("ServiceBus", "Messaging"),
    ("EventHub", "Messaging"),
    ("EventGrid", "Messaging"),
    ("NotificationHubs", "Messaging"),
    ("ApiManagement", "API Management"),
    ("Resources", "Resources"),
    ("ResourceMover", "Resources"),
    ("Cdn", "Networking"),
    ("Dns", "Networking"),
    ("FrontDoor", "Networking"),
    ("TrafficManager", "Networking"),
    ("VirtualWan", "Networking"),
    ("PowerBIEmbedded", "Analytics"),
    ("StreamAnalytics", "Analytics"),
    ("MachineLearning", "AI & ML"),
    ("CognitiveServices", "AI & ML"),
    ("DataFactory", "Data"),
    ("DataLakeStore", "Data"),
    ("Synapse", "Data"),
    ("Databricks", "Data"),
    ("Batch", "Compute"),
    ("HDInsight", "Compute"),
    ("ServiceFabric", "Compute"),
    ("Automation", "Management"),
    ("Backup", "Management"),
    ("RecoveryServices", "Management"),
    ("OperationalInsights", "Monitoring"),
]

VERB_RE = re.compile(r'^([A-Z][a-z]+)-Az')


def get_category(module_name):
    """Map Az.ModuleSuffix to a category string."""
    suffix = module_name.removeprefix("Az.")
    for key, cat in CATEGORY_MAP:
        if suffix.lower() == key.lower():
            return cat
    # Partial match fallback
    for key, cat in CATEGORY_MAP:
        if key.lower() in suffix.lower():
            return cat
    return "Other"


def parse_front_matter(text):
    """Extract YAML front matter fields as a dict."""
    m = re.match(r'^---\s*\n(.*?\n)---', text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    result = {}
    for line in block.splitlines():
        kv = line.split(':', 1)
        if len(kv) == 2:
            result[kv[0].strip()] = kv[1].strip().strip('"\'')
    return result


def extract_section(text, section_name):
    """Extract content under a ## SECTION_NAME heading."""
    pattern = rf'## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)'
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ''


def extract_code_blocks(section_text, max_blocks=3):
    """Return up to max_blocks fenced code block contents."""
    blocks = re.findall(r'```(?:powershell|ps1|posh)?\s*\n(.*?)```', section_text, re.DOTALL | re.IGNORECASE)
    cleaned = []
    for b in blocks[:max_blocks]:
        lines = [l for l in b.strip().splitlines() if not l.strip().startswith('#')]
        code = '\n'.join(lines).strip()
        if code:
            cleaned.append(code)
    return cleaned


def parse_cmdlet_doc(filepath):
    """
    Parse a single cmdlet markdown file.
    Returns dict with: name, module, syntax, description, examples
    or None if this is a module-level index file.
    """
    text = Path(filepath).read_text(encoding='utf-8', errors='replace')
    front = parse_front_matter(text)

    # Skip module index files (Az.ModuleName.md)
    fname = Path(filepath).stem
    if re.match(r'^Az\.[A-Za-z]+$', fname):
        return None

    # Cmdlet name: prefer 'title' front-matter field, fall back to filename stem
    name = front.get('title') or fname
    if not re.match(r'^[A-Z][a-z]+-Az', name):
        return None

    # Module name: prefer 'Module Name' front-matter field, fall back to Az.* parent directory
    module = front.get('Module Name', '')
    parent = Path(filepath).parent.name
    if (not module) and parent.startswith('Az.'):
        module = parent
    if not module or not module.startswith('Az.'):
        return None

    synopsis_sec = extract_section(text, 'SYNOPSIS')
    description = synopsis_sec.splitlines()[0].strip() if synopsis_sec else ''
    # Clean up markdown
    description = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', description)
    description = re.sub(r'[*_`]', '', description).strip()

    syntax_sec = extract_section(text, 'SYNTAX')
    syntax_blocks = extract_code_blocks(syntax_sec, 1)
    syntax = syntax_blocks[0] if syntax_blocks else ''

    examples_sec = extract_section(text, 'EXAMPLES')
    examples = extract_code_blocks(examples_sec, 3)

    return {
        'name': name,
        'module': module,
        'description': description,
        'syntax': syntax,
        'examples': examples,
    }


def find_latest_azps_dir(docs_root):
    """Find the highest-versioned azps-* subdirectory."""
    root = Path(docs_root)
    candidates = [d for d in root.iterdir() if d.is_dir() and d.name.startswith('azps-')]
    if not candidates:
        # Look one level deeper
        for sub in root.iterdir():
            if sub.is_dir():
                candidates += [d for d in sub.iterdir() if d.is_dir() and d.name.startswith('azps-')]
    if not candidates:
        raise FileNotFoundError(f'No azps-* directory found under {docs_root}')

    def ver_key(d):
        parts = re.findall(r'\d+', d.name)
        return tuple(int(x) for x in parts)

    return max(candidates, key=ver_key)


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_docs.py <azure-docs-powershell-root>")
        sys.exit(1)

    docs_root = sys.argv[1]
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    out_dir = repo_root / 'public' / 'data'
    modules_dir = out_dir / 'modules'
    modules_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {docs_root} ...")
    azps_dir = find_latest_azps_dir(docs_root)
    version_str = re.search(r'azps-(\d+\.\d+\.\d+)', azps_dir.name)
    version = version_str.group(1) if version_str else '0.0.0'
    print(f"Found: {azps_dir.name}  (version {version})")

    manifest_entries = []
    descriptions = {}
    modules_data = {}  # module_name -> {version, cmdlets: {}}

    # Find module version files
    module_version_map = {}
    for ver_file in azps_dir.rglob('*.md'):
        fm = parse_front_matter(ver_file.read_text(encoding='utf-8', errors='replace'))
        if 'Module Version' in fm and 'Module Name' in fm:
            mn = fm['Module Name']
            mv = fm['Module Version']
            if mn not in module_version_map:
                module_version_map[mn] = mv

    # Scan Az.* module directories
    for mod_dir in sorted(azps_dir.iterdir()):
        if not mod_dir.is_dir():
            continue
        if not mod_dir.name.startswith('Az.'):
            continue
        module_name = mod_dir.name
        mod_version = module_version_map.get(module_name, '0.0.0')
        category = get_category(module_name)
        module_cmdlets = {}

        for md_file in sorted(mod_dir.glob('*.md')):
            result = parse_cmdlet_doc(md_file)
            if not result:
                continue
            cname = result['name']
            vm = VERB_RE.match(cname)
            verb = vm.group(1) if vm else 'Other'

            manifest_entries.append({
                'n': cname,
                'v': verb,
                'm': module_name,
                'c': category,
                'e': bool(result['examples']),
            })
            if result['description']:
                descriptions[cname] = result['description']

            module_cmdlets[cname] = {
                'syntax': result['syntax'],
                'examples': result['examples'],
            }

        if module_cmdlets:
            modules_data[module_name] = {
                'module': module_name,
                'version': mod_version,
                'cmdlets': module_cmdlets,
            }

    print(f"Processed {len(manifest_entries)} cmdlets across {len(modules_data)} modules")

    # Write manifest.json
    manifest = {'v': version, 'd': manifest_entries}
    with open(out_dir / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, separators=(',', ':'))
    print(f"Wrote manifest.json ({len(manifest_entries)} entries)")

    # Write descriptions.json
    with open(out_dir / 'descriptions.json', 'w', encoding='utf-8') as f:
        json.dump(descriptions, f, indent=2, ensure_ascii=False)
    print(f"Wrote descriptions.json ({len(descriptions)} entries)")

    # Write per-module JSON files
    for mod_name, data in modules_data.items():
        out_file = modules_dir / f'{mod_name}.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
    print(f"Wrote {len(modules_data)} module JSON files to {modules_dir}")


if __name__ == '__main__':
    main()
