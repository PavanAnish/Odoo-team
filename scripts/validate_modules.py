#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module Validation Script for Odoo Subscription Management Project
Checks:
1. Existence and syntax of __manifest__.py for all addons.
2. Validation of mandatory manifest keys.
3. Python file syntax across all modules.
4. XML well-formedness for all data and view files.
5. CSV integrity for ir.model.access.csv.
6. Circular dependency check across project addons.
"""

import ast
import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADDONS_DIR = PROJECT_ROOT / 'addons'

MANDATORY_MANIFEST_KEYS = [
    'name', 'version', 'category', 'summary',
    'author', 'license', 'depends', 'data', 'installable'
]

def check_python_syntax(file_path):
    """Verify python file parses into an AST without syntax errors."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source, filename=str(file_path))
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError in {file_path}: {e}"
    except Exception as e:
        return False, f"Error reading {file_path}: {e}"

def check_xml_syntax(file_path):
    """Verify XML file is well-formed."""
    try:
        ET.parse(file_path)
        return True, None
    except ET.ParseError as e:
        return False, f"XML ParseError in {file_path}: {e}"
    except Exception as e:
        return False, f"Error reading XML {file_path}: {e}"

def check_csv_access(file_path):
    """Check ir.model.access.csv headers and columns."""
    expected_headers = ['id', 'name', 'model_id:id', 'group_id:id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink']
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers:
                return False, f"Empty CSV file: {file_path}"
            # Strip whitespace
            clean_headers = [h.strip() for h in headers]
            if clean_headers != expected_headers:
                return False, f"Invalid headers in {file_path}. Expected {expected_headers}, got {clean_headers}"
            for idx, row in enumerate(reader, start=2):
                if not row or all(not field.strip() for field in row):
                    continue
                if len(row) != len(expected_headers):
                    return False, f"Row {idx} in {file_path} has {len(row)} columns, expected {len(expected_headers)}"
        return True, None
    except Exception as e:
        return False, f"Error validating CSV {file_path}: {e}"

def validate_manifest(manifest_path):
    """Evaluate and validate __manifest__.py dictionary."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        manifest_dict = ast.literal_eval(content)
        if not isinstance(manifest_dict, dict):
            return False, f"{manifest_path} did not evaluate to a dictionary."
        missing_keys = [k for k in MANDATORY_MANIFEST_KEYS if k not in manifest_dict]
        if missing_keys:
            return False, f"Missing keys in {manifest_path}: {missing_keys}"
        return True, manifest_dict
    except Exception as e:
        return False, f"Error parsing manifest {manifest_path}: {e}"

def check_circular_dependencies(modules):
    """Topological sort to verify no cycles exist in custom module dependencies."""
    graph = {mod: set(data['depends']) for mod, data in modules.items()}
    visited = {}

    def visit(node, path):
        visited[node] = 'visiting'
        for dep in graph.get(node, []):
            if dep in graph:  # Only check within project modules
                if visited.get(dep) == 'visiting':
                    return False, f"Circular dependency detected: {' -> '.join(path + [dep])}"
                if dep not in visited:
                    res, err = visit(dep, path + [dep])
                    if not res:
                        return False, err
        visited[node] = 'visited'
        return True, None

    for mod in list(graph.keys()):
        if mod not in visited:
            res, err = visit(mod, [mod])
            if not res:
                return False, err
    return True, None

def main():
    print("=" * 70)
    print("Odoo Subscription Management - Architecture & Syntax Validator")
    print("=" * 70)

    if not ADDONS_DIR.exists():
        print(f"ERROR: Addons directory not found at {ADDONS_DIR}")
        sys.exit(1)

    modules = {}
    errors = []

    # 1. Inspect Addons
    addon_folders = [f for f in ADDONS_DIR.iterdir() if f.is_dir() and not f.name.startswith('.')]
    print(f"Found {len(addon_folders)} addon packages in {ADDONS_DIR}:")
    for f in sorted(addon_folders):
        print(f"  - {f.name}")

    print("\n--- Validating Manifests and Codebases ---")
    for addon in sorted(addon_folders):
        manifest_path = addon / '__manifest__.py'
        if not manifest_path.exists():
            errors.append(f"Missing __manifest__.py in {addon.name}")
            continue

        valid, result = validate_manifest(manifest_path)
        if not valid:
            errors.append(result)
        else:
            modules[addon.name] = result

        # Check all python files
        for py_file in addon.rglob('*.py'):
            py_ok, py_err = check_python_syntax(py_file)
            if not py_ok:
                errors.append(py_err)

        # Check all xml files
        for xml_file in addon.rglob('*.xml'):
            xml_ok, xml_err = check_xml_syntax(xml_file)
            if not xml_ok:
                errors.append(xml_err)

        # Check ir.model.access.csv if present
        csv_file = addon / 'security' / 'ir.model.access.csv'
        if csv_file.exists():
            csv_ok, csv_err = check_csv_access(csv_file)
            if not csv_ok:
                errors.append(csv_err)

    # 2. Check circular dependencies
    print("\n--- Checking Module Dependencies ---")
    dep_ok, dep_err = check_circular_dependencies(modules)
    if not dep_ok:
        errors.append(dep_err)
    else:
        print("Dependency graph verified: No circular dependencies detected.")

    print("\n" + "=" * 70)
    if errors:
        print(f"FAILED: {len(errors)} validation issue(s) detected:")
        for err in errors:
            print(f"  [X] {err}")
        sys.exit(1)
    else:
        print("SUCCESS: All module manifests, Python files, XML views, and security CSVs are valid!")
        print("=" * 70)
        sys.exit(0)

if __name__ == '__main__':
    main()
