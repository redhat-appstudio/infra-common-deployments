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
    - the ClusterRole holds exactly one rule, and that rule is exactly
      get on user.openshift.io/groups with a resourceNames list -- any extra
      or wildcard rule fails, not just a widened Groups rule
    - the ServiceAccount is bound to that ClusterRole and nothing else
    - the groupsQuery filter is in the canonical form
      (&(objectClass=rhatRoverGroup)(|(cn=...)...)), so the CNs it names are
      the only groups it can select
    - resourceNames matches the set of CNs in that filter exactly

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
# internal-production/base/rbac.yaml. Staging lands first, per the repo's
# staging-first promotion convention.
ENVIRONMENTS = ["internal-staging"]

CLUSTER_ROLE_NAME = "rover-group-sync-cr"
SERVICE_ACCOUNT_NAME = "rover-group-sync-sa"
EXPECTED_API_GROUPS = ["user.openshift.io"]
EXPECTED_RESOURCES = ["groups"]
EXPECTED_VERBS = ["get"]
BINDING_KINDS = ("RoleBinding", "ClusterRoleBinding")

# The whole filter, not just its (cn=...) terms. Anything outside this shape --
# a different outer operator, an extra term, a wildcard CN -- can select groups
# the filter does not name, which resourceNames would then deny at runtime.
CANONICAL_FILTER = re.compile(
    r"\(&\(objectClass=rhatRoverGroup\)\(\|((?:\(cn=[A-Za-z0-9._-]+\))+)\)\)"
)
CN_TERM = re.compile(r"\(cn=([A-Za-z0-9._-]+)\)")


def rbac_path(environment):
    return COMPONENT_DIR / environment / "base" / "rbac.yaml"


def ldap_config_path(environment):
    return COMPONENT_DIR / environment / "base" / "config" / "ldap-sync-config.yaml"


def load_docs(environment):
    """Return every Kubernetes document under the environment directory.

    Scanning the whole directory, not just rbac.yaml, means a ClusterRoleBinding
    that grants the ServiceAccount a second role from some other file is still
    visible to check_bindings().
    """
    env_dir = COMPONENT_DIR / environment
    if not env_dir.is_dir():
        raise FileNotFoundError(f"Missing {env_dir.relative_to(REPO_ROOT)}")

    docs = []
    for path in sorted(env_dir.rglob("*.yaml")):
        if path.name == "kustomization.yaml":
            continue
        with path.open() as handle:
            for doc in yaml.safe_load_all(handle):
                if isinstance(doc, dict) and doc.get("kind"):
                    docs.append((path, doc))
    return docs


def load_cluster_role(environment):
    """Return the rover-group-sync ClusterRole for the environment."""
    path = rbac_path(environment)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path.relative_to(REPO_ROOT)}")

    cluster_roles = [
        doc for _, doc in load_docs(environment)
        if doc.get("kind") == "ClusterRole"
        and doc.get("metadata", {}).get("name") == CLUSTER_ROLE_NAME
    ]
    if len(cluster_roles) != 1:
        raise ValueError(
            f"Expected exactly one ClusterRole/{CLUSTER_ROLE_NAME} under "
            f"{(COMPONENT_DIR / environment).relative_to(REPO_ROOT)}, "
            f"found {len(cluster_roles)}"
        )

    return cluster_roles[0]


def check_rules(rules):
    """Return a list of problems with a ClusterRole's complete rules list.

    The whole list is checked, not just the rule that happens to name
    user.openshift.io/groups: a rule with wildcard apiGroups or resources
    grants the ServiceAccount everything while leaving the Groups rule intact.
    """
    problems = []

    if not isinstance(rules, list) or len(rules) != 1:
        count = len(rules) if isinstance(rules, list) else 0
        return [
            f"the ClusterRole must hold exactly one rule (get on named Groups); "
            f"found {count}. Any additional rule widens the grant."
        ]

    rule = rules[0]
    if rule.get("apiGroups") != EXPECTED_API_GROUPS:
        problems.append(
            f"apiGroups must be {EXPECTED_API_GROUPS}, found {rule.get('apiGroups')}"
        )
    if rule.get("resources") != EXPECTED_RESOURCES:
        problems.append(
            f"resources must be {EXPECTED_RESOURCES}, found {rule.get('resources')}"
        )
    if rule.get("verbs") != EXPECTED_VERBS:
        problems.append(
            f"the CronJob never writes Groups, so verbs must be "
            f"{EXPECTED_VERBS}, found {rule.get('verbs')}"
        )

    resource_names = rule.get("resourceNames")
    if not resource_names:
        problems.append(
            "resourceNames must list the Groups the job reads; without it the "
            "rule covers every Group on the cluster"
        )
    else:
        duplicates = sorted(
            {name for name in resource_names if resource_names.count(name) > 1}
        )
        if duplicates:
            problems.append(f"duplicate resourceNames entries: {duplicates}")

    unexpected = sorted(set(rule) - {"apiGroups", "resources", "verbs", "resourceNames"})
    if unexpected:
        problems.append(f"unexpected keys on the rule: {unexpected}")

    return problems


def check_bindings(docs):
    """Return a list of problems with the roles bound to the ServiceAccount."""
    problems = []

    for path, doc in docs:
        if doc.get("kind") not in BINDING_KINDS:
            continue
        subjects = doc.get("subjects") or []
        binds_sa = any(
            subject.get("kind") == "ServiceAccount"
            and subject.get("name") == SERVICE_ACCOUNT_NAME
            for subject in subjects
            if isinstance(subject, dict)
        )
        if not binds_sa:
            continue

        role_ref = doc.get("roleRef") or {}
        if (role_ref.get("kind"), role_ref.get("name")) != ("ClusterRole", CLUSTER_ROLE_NAME):
            problems.append(
                f"{path.relative_to(REPO_ROOT)}: {doc.get('kind')}/"
                f"{doc.get('metadata', {}).get('name')} binds "
                f"{SERVICE_ACCOUNT_NAME} to {role_ref.get('kind')}/"
                f"{role_ref.get('name')}; the ServiceAccount must only hold "
                f"ClusterRole/{CLUSTER_ROLE_NAME}"
            )

    return problems


def extract_cns(ldap_filter):
    """Return the CNs selected by a groupsQuery filter in canonical form.

    Raises ValueError if the filter is not exactly an objectClass term ANDed
    with a disjunction of literal CNs. A filter can select groups it does not
    name -- flipping the outer & to | selects every rhatRoverGroup in the
    baseDN -- and scraping (cn=...) substrings would not notice, so the shape
    is validated rather than the terms alone.
    """
    if not isinstance(ldap_filter, str):
        raise ValueError(f"groupsQuery filter must be a string, found {ldap_filter!r}")

    match = CANONICAL_FILTER.fullmatch(ldap_filter.strip())
    if not match:
        raise ValueError(
            "groupsQuery filter is not in the canonical form "
            "(&(objectClass=rhatRoverGroup)(|(cn=...)...)): "
            f"{ldap_filter!r}. Only that form is guaranteed to select exactly "
            "the CNs it names, which is what resourceNames is pinned to. If "
            "the filter genuinely has to change shape, update CANONICAL_FILTER "
            "and re-derive resourceNames together."
        )

    cns = CN_TERM.findall(match.group(1))
    duplicates = sorted({cn for cn in cns if cns.count(cn) > 1})
    if duplicates:
        raise ValueError(f"duplicate (cn=...) terms in the groupsQuery filter: {duplicates}")

    return set(cns)


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

    try:
        return extract_cns(ldap_filter)
    except ValueError as exc:
        raise ValueError(f"{path.relative_to(REPO_ROOT)}: {exc}") from exc


class TestRoverGroupSyncRBAC(unittest.TestCase):
    """Least-privilege checks for the rover-group-sync ClusterRole."""

    def test_cluster_role_grants_only_get_on_named_groups(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                rules = load_cluster_role(environment).get("rules")
                self.assertEqual(
                    check_rules(rules), [],
                    f"{environment}: {rbac_path(environment).relative_to(REPO_ROOT)}",
                )

    def test_service_account_holds_no_other_role(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                self.assertEqual(check_bindings(load_docs(environment)), [])

    def test_resource_names_match_ldap_filter(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment):
                rule = load_cluster_role(environment)["rules"][0]
                resource_names = set(rule.get("resourceNames") or [])
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


class TestChecksCatchWidening(unittest.TestCase):
    """The checks above are only worth running if they reject widened input."""

    GOOD_RULE = {
        "apiGroups": ["user.openshift.io"],
        "resources": ["groups"],
        "verbs": ["get"],
        "resourceNames": ["konflux-admins"],
    }
    GOOD_FILTER = "(&(objectClass=rhatRoverGroup)(|(cn=konflux-admins)(cn=konflux-sre)))"

    def test_canonical_input_passes(self):
        self.assertEqual(check_rules([self.GOOD_RULE]), [])
        self.assertEqual(extract_cns(self.GOOD_FILTER), {"konflux-admins", "konflux-sre"})

    def test_extra_wildcard_rule_is_rejected(self):
        wildcard = {"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]}
        self.assertTrue(check_rules([self.GOOD_RULE, wildcard]))

    def test_widened_verbs_are_rejected(self):
        self.assertTrue(check_rules([{**self.GOOD_RULE, "verbs": ["get", "patch"]}]))

    def test_missing_resource_names_is_rejected(self):
        unnamed = {key: value for key, value in self.GOOD_RULE.items() if key != "resourceNames"}
        self.assertTrue(check_rules([unnamed]))

    def test_duplicate_resource_names_are_rejected(self):
        duplicated = {**self.GOOD_RULE, "resourceNames": ["konflux-admins", "konflux-admins"]}
        self.assertTrue(check_rules([duplicated]))

    def test_second_binding_is_rejected(self):
        docs = [(
            REPO_ROOT / "fake.yaml",
            {
                "kind": "ClusterRoleBinding",
                "metadata": {"name": "extra"},
                "roleRef": {"kind": "ClusterRole", "name": "cluster-admin"},
                "subjects": [{"kind": "ServiceAccount", "name": SERVICE_ACCOUNT_NAME}],
            },
        )]
        self.assertTrue(check_bindings(docs))

    def test_disjunctive_outer_filter_is_rejected(self):
        # Same CN terms, but this selects every rhatRoverGroup in the baseDN.
        widened = self.GOOD_FILTER.replace("(&(objectClass", "(|(objectClass")
        self.assertEqual(CN_TERM.findall(widened), CN_TERM.findall(self.GOOD_FILTER))
        with self.assertRaises(ValueError):
            extract_cns(widened)

    def test_extra_filter_term_is_rejected(self):
        widened = self.GOOD_FILTER[:-1] + "(objectClass=groupOfUniqueNames))"
        with self.assertRaises(ValueError):
            extract_cns(widened)

    def test_wildcard_cn_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_cns("(&(objectClass=rhatRoverGroup)(|(cn=konflux-*)))")

    def test_duplicate_cn_terms_are_rejected(self):
        with self.assertRaises(ValueError):
            extract_cns("(&(objectClass=rhatRoverGroup)(|(cn=konflux-sre)(cn=konflux-sre)))")


def check_prerequisites(should_print=False):
    """Verify every environment's files parse, and report what was found."""
    summary = {}
    for environment in ENVIRONMENTS:
        rules = load_cluster_role(environment).get("rules") or [{}]
        cns = load_ldap_cns(environment)
        summary[environment] = (rules, cns)

        if should_print:
            print(f"✓ {environment}")
            print(f"    {rbac_path(environment).relative_to(REPO_ROOT)}")
            print(f"      rules: {len(rules)}")
            print(f"      verbs: {rules[0].get('verbs')}")
            print(f"      resourceNames: {len(rules[0].get('resourceNames') or [])}")
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
