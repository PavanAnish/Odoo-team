#!/usr/bin/env bash
# ==============================================================================
# Test Runner Script for Odoo Subscription Management
# Runs linting, syntax validation, and Odoo unit test suites.
# ==============================================================================

set -e

echo "=== Running Subscription Management Test Suite ==="

# 1. Manifest and Syntax Validation
python3 scripts/validate_modules.py

# 2. Check if odoo-bin is available to execute full test suite
if command -v odoo-bin &> /dev/null || [ -f "odoo-bin" ]; then
    ODOO_BIN=${ODOO_BIN:-"odoo-bin"}
    echo "Running Odoo test tags for subscription modules..."
    $ODOO_BIN -c config/odoo.conf \
        -d subscription_test_db \
        -i subscription_base,subscription_auth,subscription_catalog,subscription_management,subscription_billing,subscription_reports,subscription_module_template \
        --test-enable \
        --test-tags=subscription \
        --stop-after-init
else
    echo "NOTICE: 'odoo-bin' not found in PATH or project root."
    echo "Unit test syntax and structural integrity validated via Python AST."
    echo "To run dynamic database integration tests, install Odoo and execute with a running PostgreSQL server."
fi

echo "=== Test Suite Validation Complete ==="
