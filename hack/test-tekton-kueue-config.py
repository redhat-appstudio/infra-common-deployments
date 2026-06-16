#!/usr/bin/env python3
"""
Tekton-Kueue Configuration Test - infra-common Deployments

A test suite that validates the CEL expressions in the tekton-kueue configuration for
infra-common internal clusters by:

1. **Reading configuration dynamically** from internal-staging and internal-production configs
2. **Getting the image** from kustomization files
3. **Running mutations** using the actual tekton-kueue container via podman
4. **Validating results** against expected queue name and priority class

Test Coverage:
    - Default priority class assignment (konflux-default)
    - Queue name assignment (pipelines-queue)
    - Rate-limiting labels for signing-server resource allocation:
      * Both labels present with correct values (allocates signing-server-request)
      * Partial labels (rate-limited only, group only)
      * Invalid label values (rate-limited=false, wrong group)
      * Label preservation through mutation

Environments:
    - internal-staging: 300 concurrent pipeline quota
    - internal-production: 500 concurrent pipeline quota

Note: infra-common uses a simplified kueue configuration with basic queue
assignment, default priority, and conditional signing-server resource allocation
based on rate-limiting labels. Platform detection and event-type routing are not used.

Usage:
    # Check if all prerequisites are met
    python hack/test-tekton-kueue-config.py --check-setup

    # Run all tests
    python hack/test-tekton-kueue-config.py

    # Run tests with verbose output
    python hack/test-tekton-kueue-config.py --verbose

Prerequisites:
    - Python 3 with PyYAML
    - Podman (for running the tekton-kueue container)
    - Access to the tekton-kueue images specified in the kustomizations

CI/CD Integration:
    The test runs automatically on pull requests via the GitHub action
    `.github/workflows/test-tekton-kueue-config.yaml` when:
    - Changes are made to `components/kueue/**`
    - The test script itself is modified
    - The workflow file is modified

    The test will **FAIL** (not skip) if any prerequisites are missing, ensuring
    issues are caught early in CI/CD pipelines.
"""

import subprocess
import tempfile
import os
import yaml
import unittest
from pathlib import Path
from typing import Dict, Any, TypedDict
from dataclasses import dataclass
import sys


@dataclass
class TestConfig:
    config_file: Path
    kustomization_file: Path
    image: str


class ConfigCombination(TypedDict):
    config_file: str
    kustomization_file: str


class TestCombination(TypedDict):
    pipelinerun_key: str
    config_key: str
    expected: ExpectedResults | None


class PipelineRunMetadata(TypedDict, total=False):
    name: str
    namespace: str
    labels: Dict[str, str]
    annotations: Dict[str, str]


class PipelineRunDefinition(TypedDict):
    apiVersion: str
    kind: str
    metadata: PipelineRunMetadata
    spec: Dict[str, Any]  # More flexible since PipelineRun specs can vary


class ExpectedResults(TypedDict):
    annotations: Dict[str, str]
    labels: Dict[str, str]


class PipelineRunTestData(TypedDict):
    pipelinerun: PipelineRunDefinition
    expected: ExpectedResults


def get_tekton_kueue_image(kustomization_file: Path) -> str:
    """Read the tekton-kueue image from the given kustomization file."""
    try:
        with open(kustomization_file, 'r') as f:
            kustomization = yaml.safe_load(f)

        # Look for the tekton-kueue image in the images section
        images = kustomization.get('images', [])
        for image in images:
            if image.get('name') == 'konflux-ci/tekton-kueue':
                new_name = image.get('newName', '')
                new_tag = image.get('newTag', '')
                if new_name and new_tag:
                    return f"{new_name}:{new_tag}"

        raise ValueError("tekton-kueue image not found in kustomization")

    except Exception as e:
        raise RuntimeError(f"Failed to read tekton-kueue image from {kustomization_file}: {e}")

def resolve_path(path_str: str, repo_root: Path) -> Path:
    """Resolve a path string to an absolute Path, handling both relative and absolute paths."""
    if Path(path_str).is_absolute():
        return Path(path_str)
    return repo_root / path_str


def validate_config_combination(config_key: str, repo_root: Path) -> TestConfig:
    """Validate and resolve config and kustomization files for a config combination."""
    config_data = CONFIG_COMBINATIONS[config_key]

    config_file = resolve_path(config_data["config_file"], repo_root)
    kustomization_file = resolve_path(config_data["kustomization_file"], repo_root)

    # Validate files exist
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found for config '{config_key}': {config_file}")

    if not kustomization_file.exists():
        raise FileNotFoundError(f"Kustomization file not found for config '{config_key}': {kustomization_file}")

    # Get image from kustomization
    image = get_tekton_kueue_image(kustomization_file)

    return TestConfig(
        config_file=config_file,
        kustomization_file=kustomization_file,
        image=image
    )


def check_prerequisites(should_print: bool = True) -> Dict[str, TestConfig]:
    """Check that all prerequisites are available and pre-process config combinations."""
    messages = ["Checking prerequisites..."]
    repo_root = Path(__file__).parent.parent

    # Check podman availability
    try:
        result = subprocess.run(["podman", "--version"], capture_output=True, check=True, text=True)
        podman_version = result.stdout.strip()
        messages.append(f"✓ Podman available: {podman_version}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Podman not available")

    # Pre-process all unique config combinations
    processed_configs: Dict[str, TestConfig] = {}

    for _, test_combination in TEST_COMBINATIONS.items():
        config_key = test_combination["config_key"]

        # Only process each config combination once
        if config_key not in processed_configs:
            try:
                config = validate_config_combination(config_key, repo_root)
                processed_configs[config_key] = config
                messages.append(f"✓ Config '{config_key}': {config.config_file}, image={config.image}")
            except Exception as e:
                raise RuntimeError(f"Config '{config_key}' validation failed: {e}")

    if should_print:
        for message in messages:
            print(message)

    return processed_configs

# Test PipelineRun definitions (reusable across different configs)
PIPELINERUN_DEFINITIONS: Dict[str, PipelineRunTestData] = {
    "default_priority": {
        "name": "Default pipeline (no special labels)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-default",
                "namespace": "default"
            },
            "spec": {
                "pipelineRef": {"name": "default-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "internal_pipelinerun_child": {
        "name": "Internal-pipelinerun child pipeline (e.g., signing pipeline)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-internal-pipelinerun-child",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/pipelinerun-uid": "12345678-1234-1234-1234-123456789012"
                }
            },
            "spec": {
                "pipelineRef": {"name": "signing-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "rate_limited_signing_server": {
        "name": "Rate-limited pipeline with signing-server group (should allocate signing-server-request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limited-signing-server",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "true",
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "signing-server"
                }
            },
            "spec": {
                "pipelineRef": {"name": "signing-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {
                'kueue.konflux-ci.dev/requests-signing-server-request': '1'
            },
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "rate_limited_only": {
        "name": "Rate-limited label only without group (should NOT allocate signing-server-request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limited-only",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "true"
                }
            },
            "spec": {
                "pipelineRef": {"name": "test-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "rate_limiting_group_only": {
        "name": "Rate-limiting group only without rate-limited flag (should NOT allocate signing-server-request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limiting-group-only",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "signing-server"
                }
            },
            "spec": {
                "pipelineRef": {"name": "test-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "rate_limited_false": {
        "name": "Rate-limited set to false with signing-server group (should NOT allocate signing-server-request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limited-false",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "false",
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "signing-server"
                }
            },
            "spec": {
                "pipelineRef": {"name": "test-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "rate_limiting_wrong_group": {
        "name": "Rate-limited with different group (should NOT allocate signing-server-request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limiting-wrong-group",
                "namespace": "default",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "true",
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "other-service"
                }
            },
            "spec": {
                "pipelineRef": {"name": "test-pipeline"},
                "workspaces": [{"name": "shared-workspace", "emptyDir": {}}]
            }
        },
        "expected": {
            "annotations": {},
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    }
}

# Configuration combinations that can be applied to any PipelineRun
CONFIG_COMBINATIONS: Dict[str, ConfigCombination] = {
    "internal-staging": {
        "name": "Internal Staging config",
        "config_file": "components/kueue/internal-staging/tekton-kueue/config.yaml",
        "kustomization_file": "components/kueue/internal-staging/tekton-kueue/kustomization.yaml"
    },
    "internal-production": {
        "name": "Internal Production config",
        "config_file": "components/kueue/internal-production/tekton-kueue/config.yaml",
        "kustomization_file": "components/kueue/internal-production/tekton-kueue/kustomization.yaml"
    }
}

# Test combinations: which PipelineRuns to test with which configs
TEST_COMBINATIONS: Dict[str, TestCombination] = {
    "default_priority_internal_staging": {
        "pipelinerun_key": "default_priority",
        "config_key": "internal-staging"
    },
    "default_priority_internal_production": {
        "pipelinerun_key": "default_priority",
        "config_key": "internal-production"
    },
    "internal_pipelinerun_child_internal_staging": {
        "pipelinerun_key": "internal_pipelinerun_child",
        "config_key": "internal-staging"
    },
    "internal_pipelinerun_child_internal_production": {
        "pipelinerun_key": "internal_pipelinerun_child",
        "config_key": "internal-production"
    },
    "rate_limited_signing_server_internal_staging": {
        "pipelinerun_key": "rate_limited_signing_server",
        "config_key": "internal-staging"
    },
    "rate_limited_signing_server_internal_production": {
        "pipelinerun_key": "rate_limited_signing_server",
        "config_key": "internal-production"
    },
    "rate_limited_only_internal_staging": {
        "pipelinerun_key": "rate_limited_only",
        "config_key": "internal-staging"
    },
    "rate_limited_only_internal_production": {
        "pipelinerun_key": "rate_limited_only",
        "config_key": "internal-production"
    },
    "rate_limiting_group_only_internal_staging": {
        "pipelinerun_key": "rate_limiting_group_only",
        "config_key": "internal-staging"
    },
    "rate_limiting_group_only_internal_production": {
        "pipelinerun_key": "rate_limiting_group_only",
        "config_key": "internal-production"
    },
    "rate_limited_false_internal_staging": {
        "pipelinerun_key": "rate_limited_false",
        "config_key": "internal-staging"
    },
    "rate_limited_false_internal_production": {
        "pipelinerun_key": "rate_limited_false",
        "config_key": "internal-production"
    },
    "rate_limiting_wrong_group_internal_staging": {
        "pipelinerun_key": "rate_limiting_wrong_group",
        "config_key": "internal-staging"
    },
    "rate_limiting_wrong_group_internal_production": {
        "pipelinerun_key": "rate_limiting_wrong_group",
        "config_key": "internal-production"
    }
}


class TektonKueueMutationTest(unittest.TestCase):
    """Test suite for tekton-kueue CEL expression mutations."""

    @classmethod
    def setUpClass(cls):
        """Set up test class - check prerequisites and pre-process configs."""
        cls.processed_configs = check_prerequisites(should_print=False)
        cls.repo_root = Path(__file__).parent.parent
        print("Prerequisites validated for all tests.")

    def run_mutation_test(self, test_combination: TestCombination) -> Dict[str, Any]:
        """Run a single mutation test and return results."""
        # Get pre-processed configuration
        config_key = test_combination["config_key"]
        test_config = self.processed_configs[config_key]

        # Get the PipelineRun definition
        pipelinerun_key = test_combination["pipelinerun_key"]
        pipelinerun_data = PIPELINERUN_DEFINITIONS[pipelinerun_key]
        if "expected" in test_combination and test_combination["expected"] is not None:
            pipelinerun_data["expected"] = test_combination["expected"]

        pipelinerun = pipelinerun_data["pipelinerun"]

        with tempfile.TemporaryDirectory() as temp_dir:
            # Write the config file
            config_path = Path(temp_dir) / "config.yaml"
            pipelinerun_path = Path(temp_dir) / "pipelinerun.yaml"

            # Copy the test-specific config file
            import shutil
            shutil.copy2(test_config.config_file, config_path)

            # Write the PipelineRun
            with open(pipelinerun_path, 'w') as f:
                yaml.dump(pipelinerun, f, default_flow_style=False)

            # Set proper permissions
            os.chmod(config_path, 0o644)
            os.chmod(pipelinerun_path, 0o644)
            os.chmod(temp_dir, 0o755)

            # Run the mutation with test-specific image
            cmd = [
                "podman", "run", "--rm",
                "-v", f"{temp_dir}:/workspace:z",
                test_config.image,
                "mutate",
                "--pipelinerun-file", "/workspace/pipelinerun.yaml",
                "--config-dir", "/workspace"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                self.fail(f"Mutation failed: {result.stderr}")

            # Parse the mutated PipelineRun
            try:
                mutated = yaml.safe_load(result.stdout)
            except yaml.YAMLError as e:
                self.fail(f"Failed to parse mutated YAML: {e}")

            return mutated

    def validate_mutation_result(self, test_key: str, test_combination: TestCombination) -> None:
        """Helper method to validate mutation results."""
        with self.subTest(test=test_key):
            # Get pre-processed configuration for logging
            config_key = test_combination["config_key"]
            test_config = self.processed_configs[config_key]
            print(f"Running test '{test_key}' with config: {test_config.config_file}, image: {test_config.image}")

            mutated = self.run_mutation_test(test_combination)

            # Get expected results from the PipelineRun definition
            pipelinerun_key = test_combination["pipelinerun_key"]
            pipelinerun_data = PIPELINERUN_DEFINITIONS[pipelinerun_key]
            expected = pipelinerun_data["expected"]

            original_metadata = pipelinerun_data["pipelinerun"].get("metadata", {})
            original_annotations = original_metadata.get("annotations", {}) or {}
            original_labels = original_metadata.get("labels", {}) or {}

            # Check annotations (full equality vs original + expected)
            annotations = mutated.get("metadata", {}).get("annotations", {})
            expected_annotations = expected["annotations"]
            expected_annotations_full = {**original_annotations, **expected_annotations}
            self.assertDictEqual(
                annotations,
                expected_annotations_full,
                f"Annotations mismatch; expected {expected_annotations_full}, got {annotations}"
            )

            # Check labels (full equality vs original + expected)
            labels = mutated.get("metadata", {}).get("labels", {})
            expected_labels = expected["labels"]
            expected_labels_full = {**original_labels, **expected_labels}
            self.assertDictEqual(
                labels,
                expected_labels_full,
                f"Labels mismatch; expected {expected_labels_full}, got {labels}"
            )

    def test_all_mutations(self):
        """Test all tekton-kueue mutation scenarios."""
        for test_key, test_combination in TEST_COMBINATIONS.items():
            self.validate_mutation_result(test_key, test_combination)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test tekton-kueue CEL expressions")
    parser.add_argument("--check-setup", action="store_true",
                       help="Check if prerequisites are met and show configuration")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Run tests with verbose output")

    # Parse known args to allow unittest args to pass through
    args, unknown = parser.parse_known_args()

    if args.check_setup:
        try:
            processed_configs = check_prerequisites(should_print=True)
        except Exception as e:
            print(f"✗ {e}")
            sys.exit(1)

        print("\n✅ All prerequisites met! Ready to run tests.")
        print("Run: python hack/test-tekton-kueue-config.py")
        print("\nNote: Tests will FAIL (not skip) if any prerequisites are missing.")

    else:
        # Run unittest with remaining args
        verbosity = 2 if args.verbose else 1
        sys.argv = [sys.argv[0]] + unknown
        unittest.main(verbosity=verbosity)
