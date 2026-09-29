#!/usr/bin/env python3
"""
Rover Group Sync RBAC Test - infra-common Deployments

Validates that the rover-group-sync ClusterRole stays least-privilege and in
sync with the LDAP groups it actually reads.

The CronJob runs `oc adm groups sync` without --confirm, so it only GETs each
OpenShift Group by name (groupNameAttributes is `cn`, so the Group object name
equals the LDAP CN). The ClusterRole is therefore restricted to verbs ["get"]
with an explicit resourceNames list. That list has to track the CNs in the
groupsQuery filter of config/ldap-sync-config.yaml: if a CN is added to the
filter without being added to resourceNames, the GET returns 403 and the sync
run fails.

Checks, per environment:
    - the ClusterRole grants only the "get" verb
    - resourceNames is present and non-empty
    - resourceNames matches the set of CNs in the LDAP filter exactly

Usage:
    # Check if all prerequisites are met
    python hack/test-rover-group-sync-rbac.py --check-setup

    # Run all tests
    python hack/test-rover-group-sync-rbac.py

    # Run tests with verbose output
    python hack/test-rover-group-sync-rbac.py --verbose

Prerequisites:
    - PyYAML
"""

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_DIR = REPO_ROOT / "components" / "rover-group-sync"

# Add "internal-production" here in the same change that tightens
# internal-production/base/rbac.yaml (staging-first promotion, see
# skills/pr-workflow.md).
ENVIRONMENTS = ["internal-staging"]

CLUSTER_ROLE_NAME = "rover-group-sync-cr"
EXPECTED_VERBS = ["get"]
CN_PATTERN = re.compile(r"\(cn=([^)]+)\)")


def rbac_path(environment):
    return COMPONENT_DIR / environment / "base" / "rbac.yaml"


def ldap_config_path(environment):
    return COMPONENT_DIR / environment / "base" / "config" / "ldap-sync-config.yaml"


def load_group_rule(environment):
    """Return the user.openshift.io/groups rule from the environment's ClusterRole."""
    path = rbac_path(environment)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path.relative_to(REPO_ROOT)}")

    with path.open() as handle:
        docs = [doc for doc in yaml.safe_load_all(handle) if doc]

    cluster_roles = [
        doc for doc in docs
        if doc.get("kind") == "ClusterRole"
        and doc.get("metadata", {}).get("name") == CLUSTER_ROLE_NAME
    ]
    if len(cluster_roles) != 1:
        raise ValueError(
            f"Expected exactly one ClusterRole/{CLUSTER_ROLE_NAME} in "
            f"{path.relative_to(REPO_ROOT)}, found {len(cluster_roles)}"
        )

    rules = [
        rule for rule in cluster_roles[0].get("rules", [])
        if "user.openshift.io" in rule.get("apiGroups", [])
        and "groups" in rule.get("resources", [])
    ]
    if len(rules) != 1:
        raise ValueError(
            f"Expected exactly one user.openshift.io/groups rule in "
            f"{path.relative_to(REPO_ROOT)}, found {len(rules)}"
        )

    return rules[0]


def load_ldap_cns(environment):
    """Return the set of CNs matched by the environment's groupsQuery filter."""
    path = ldap_config_path(environment)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path.relative_to(REPO_ROOT)}")

    with path.open() as handle:
        config = yaml.safe_load(handle)

    try:
        ldap_filter = config["rfc2307"]["groupsQuery"]["filter"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"No rfc2307.groupsQuery.filter in {path.relative_to(REPO_ROOT)}"
        ) from exc

    cns = CN_PATTERN.findall(ldap_filter)
    if not cns:
        raise ValueError(
            f"No (cn=...) terms in the groupsQuery filter of "
            f"{path.relative_to(REPO_ROOT)}"
        )

    return set(cns)


class TestRoverGroupSyncRBAC(unittest.TestCase):
    """Least-privilege checks for the rover-group-sync ClusterRole."""

    def test_verbs_are_get_only(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                rule = load_group_rule(environment)
                self.assertEqual(
                    rule.get("verbs"), EXPECTED_VERBS,
                    f"{environment}: the CronJob never writes Groups, so verbs "
                    f"must be {EXPECTED_VERBS}",
                )

    def test_resource_names_present(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                rule = load_group_rule(environment)
                self.assertTrue(
                    rule.get("resourceNames"),
                    f"{environment}: resourceNames must list the Groups the job "
                    f"reads; without it the rule covers every Group on the cluster",
                )

    def test_resource_names_match_ldap_filter(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                resource_names = set(load_group_rule(environment).get("resourceNames", []))
                cns = load_ldap_cns(environment)

                missing = sorted(cns - resource_names)
                extra = sorted(resource_names - cns)

                self.assertFalse(
                    missing,
                    f"{environment}: CNs in the LDAP filter with no matching "
                    f"resourceNames entry (the sync will 403 on these): {missing}",
                )
                self.assertFalse(
                    extra,
                    f"{environment}: resourceNames entries that are not in the "
                    f"LDAP filter (stale grants): {extra}",
                )

    def test_resource_names_have_no_duplicates(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                resource_names = load_group_rule(environment).get("resourceNames", [])
                duplicates = sorted(
                    {name for name in resource_names if resource_names.count(name) > 1}
                )
                self.assertFalse(
                    duplicates,
                    f"{environment}: duplicate resourceNames entries: {duplicates}",
                )


def check_prerequisites(should_print=False):
    """Verify every environment's files parse, and report what was found."""
    summary = {}
    for environment in ENVIRONMENTS:
        rule = load_group_rule(environment)
        cns = load_ldap_cns(environment)
        summary[environment] = (rule, cns)

        if should_print:
            print(f"✓ {environment}")
            print(f"    {rbac_path(environment).relative_to(REPO_ROOT)}")
            print(f"      verbs: {rule.get('verbs')}")
            print(f"      resourceNames: {len(rule.get('resourceNames') or [])}")
            print(f"    {ldap_config_path(environment).relative_to(REPO_ROOT)}")
            print(f"      filter CNs: {len(cns)}")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test rover-group-sync ClusterRole least-privilege"
    )
    parser.add_argument("--check-setup", action="store_true",
                        help="Check if prerequisites are met and show configuration")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Run tests with verbose output")

    # Parse known args to allow unittest args to pass through
    args, unknown = parser.parse_known_args()

    if args.check_setup:
        try:
            check_prerequisites(should_print=True)
        except Exception as e:
            print(f"✗ {e}")
            sys.exit(1)

        print("\n✅ All prerequisites met! Ready to run tests.")
        print("Run: python hack/test-rover-group-sync-rbac.py")

    else:
        verbosity = 2 if args.verbose else 1
        sys.argv = [sys.argv[0]] + unknown
        unittest.main(verbosity=verbosity)
