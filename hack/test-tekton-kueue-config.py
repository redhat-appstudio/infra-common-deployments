#!/usr/bin/env python3
"""
Tekton-Kueue Configuration Test for infra-common-deployments

Validates CEL expressions in the tekton-kueue configuration by:

1. Reading configuration dynamically from internal-staging/production config files
2. Getting the container image from the corresponding kustomization files
3. Running mutations using the actual tekton-kueue container via podman
4. Validating results against expected annotations, labels, and priority classes

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
    - Access to the tekton-kueue image specified in kustomization files
"""

import subprocess
import tempfile
import os
import shutil
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
    name: str
    config_file: str
    kustomization_file: str


class TestCombination(TypedDict):
    pipelinerun_key: str
    config_key: str


class PipelineRunMetadata(TypedDict, total=False):
    name: str
    namespace: str
    labels: Dict[str, str]
    annotations: Dict[str, str]


class PipelineRunDefinition(TypedDict):
    apiVersion: str
    kind: str
    metadata: PipelineRunMetadata
    spec: Dict[str, Any]


class ExpectedResults(TypedDict):
    annotations: Dict[str, str]
    labels: Dict[str, str]


class PipelineRunTestData(TypedDict):
    name: str
    pipelinerun: PipelineRunDefinition
    expected: ExpectedResults


def get_tekton_kueue_image(kustomization_file: Path) -> str:
    """Read the tekton-kueue image from the given kustomization file."""
    try:
        with open(kustomization_file, 'r') as f:
            kustomization = yaml.safe_load(f)

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
    """Resolve a path string to an absolute Path."""
    if Path(path_str).is_absolute():
        return Path(path_str)
    return repo_root / path_str


def validate_config_combination(config_key: str, repo_root: Path) -> TestConfig:
    """Validate and resolve config and kustomization files for a config combination."""
    config_data = CONFIG_COMBINATIONS[config_key]

    config_file = resolve_path(config_data["config_file"], repo_root)
    kustomization_file = resolve_path(config_data["kustomization_file"], repo_root)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found for '{config_key}': {config_file}")

    if not kustomization_file.exists():
        raise FileNotFoundError(f"Kustomization file not found for '{config_key}': {kustomization_file}")

    image = get_tekton_kueue_image(kustomization_file)

    return TestConfig(
        config_file=config_file,
        kustomization_file=kustomization_file,
        image=image
    )


def check_prerequisites(should_print: bool = True) -> Dict[str, TestConfig]:
    """Check that all prerequisites are available and pre-process config combinations.

    Tolerates missing config environments (e.g. production not yet merged) and
    skips them with a warning. Fails only if no configs are available at all.
    """
    messages = ["Checking prerequisites..."]
    repo_root = Path(__file__).parent.parent

    try:
        result = subprocess.run(["podman", "--version"], capture_output=True, check=True, text=True)
        podman_version = result.stdout.strip()
        messages.append(f"✓ Podman available: {podman_version}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Podman not available. Install podman to run these tests.")

    processed_configs: Dict[str, TestConfig] = {}

    for config_key in CONFIG_COMBINATIONS:
        try:
            config = validate_config_combination(config_key, repo_root)
            processed_configs[config_key] = config
            messages.append(f"✓ Config '{config_key}': {config.config_file.relative_to(repo_root)}, image={config.image}")
        except FileNotFoundError as e:
            messages.append(f"⚠ Config '{config_key}' skipped (files not present): {e}")
        except Exception as e:
            raise RuntimeError(f"Config '{config_key}' validation failed: {e}")

    if not processed_configs:
        raise RuntimeError("No valid config combinations found. At least one environment must be present.")

    if should_print:
        for message in messages:
            print(message)

    return processed_configs


# ---------------------------------------------------------------------------
# PipelineRun test definitions
# ---------------------------------------------------------------------------

PIPELINERUN_DEFINITIONS: Dict[str, PipelineRunTestData] = {
    "signing_pipeline": {
        "name": "Signing pipeline with rate-limiting labels",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-signing-pipeline",
                "namespace": "internal-services",
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
                "kueue.konflux-ci.dev/requests-signing-server-request": "1"
            },
            "labels": {
                "kueue.x-k8s.io/queue-name": "pipelines-queue",
                "kueue.x-k8s.io/priority-class": "konflux-default"
            }
        }
    },

    "non_signing_pipeline": {
        "name": "Regular pipeline without rate-limiting labels",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-regular-pipeline",
                "namespace": "internal-services",
                "labels": {}
            },
            "spec": {
                "pipelineRef": {"name": "some-pipeline"},
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

    "partial_labels_pipeline": {
        "name": "Pipeline with rate-limited=true but wrong group",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-partial-labels",
                "namespace": "internal-services",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "true",
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "other-service"
                }
            },
            "spec": {
                "pipelineRef": {"name": "other-pipeline"},
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

    "no_labels_pipeline": {
        "name": "Minimal pipeline with no labels at all",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-no-labels",
                "namespace": "internal-services"
            },
            "spec": {
                "pipelineRef": {"name": "minimal-pipeline"},
                "workspaces": [{"name": "ws", "emptyDir": {}}]
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
        "name": "Pipeline with rate-limited=false (should not get resource request)",
        "pipelinerun": {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {
                "name": "test-rate-limited-false",
                "namespace": "internal-services",
                "labels": {
                    "internal-services.appstudio.openshift.io/rate-limited": "false",
                    "internal-services.appstudio.openshift.io/rate-limiting-group": "signing-server"
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
    }
}


# ---------------------------------------------------------------------------
# Configuration combinations (environments)
# ---------------------------------------------------------------------------

CONFIG_COMBINATIONS: Dict[str, ConfigCombination] = {
    "internal-staging": {
        "name": "Internal Staging",
        "config_file": "components/kueue/internal-staging/tekton-kueue/config.yaml",
        "kustomization_file": "components/kueue/internal-staging/tekton-kueue/kustomization.yaml"
    },
    "internal-production": {
        "name": "Internal Production",
        "config_file": "components/kueue/internal-production/tekton-kueue/config.yaml",
        "kustomization_file": "components/kueue/internal-production/tekton-kueue/kustomization.yaml"
    }
}


# ---------------------------------------------------------------------------
# Test combinations: which PipelineRuns to test with which configs
# ---------------------------------------------------------------------------

TEST_COMBINATIONS: Dict[str, TestCombination] = {
    # Internal Staging tests
    "signing_pipeline_staging": {
        "pipelinerun_key": "signing_pipeline",
        "config_key": "internal-staging"
    },
    "non_signing_pipeline_staging": {
        "pipelinerun_key": "non_signing_pipeline",
        "config_key": "internal-staging"
    },
    "partial_labels_pipeline_staging": {
        "pipelinerun_key": "partial_labels_pipeline",
        "config_key": "internal-staging"
    },
    "no_labels_pipeline_staging": {
        "pipelinerun_key": "no_labels_pipeline",
        "config_key": "internal-staging"
    },
    "rate_limited_false_staging": {
        "pipelinerun_key": "rate_limited_false",
        "config_key": "internal-staging"
    },

    # Internal Production tests
    "signing_pipeline_production": {
        "pipelinerun_key": "signing_pipeline",
        "config_key": "internal-production"
    },
    "non_signing_pipeline_production": {
        "pipelinerun_key": "non_signing_pipeline",
        "config_key": "internal-production"
    },
    "partial_labels_pipeline_production": {
        "pipelinerun_key": "partial_labels_pipeline",
        "config_key": "internal-production"
    },
    "no_labels_pipeline_production": {
        "pipelinerun_key": "no_labels_pipeline",
        "config_key": "internal-production"
    },
    "rate_limited_false_production": {
        "pipelinerun_key": "rate_limited_false",
        "config_key": "internal-production"
    }
}


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

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
        config_key = test_combination["config_key"]
        test_config = self.processed_configs[config_key]

        pipelinerun_key = test_combination["pipelinerun_key"]
        pipelinerun_data = PIPELINERUN_DEFINITIONS[pipelinerun_key]
        pipelinerun = pipelinerun_data["pipelinerun"]

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            pipelinerun_path = Path(temp_dir) / "pipelinerun.yaml"

            shutil.copy2(test_config.config_file, config_path)

            with open(pipelinerun_path, 'w') as f:
                yaml.dump(pipelinerun, f, default_flow_style=False)

            os.chmod(config_path, 0o644)
            os.chmod(pipelinerun_path, 0o644)
            os.chmod(temp_dir, 0o755)

            cmd = [
                "podman", "run", "--rm",
                "-v", f"{temp_dir}:/workspace:z",
                test_config.image,
                "mutate",
                "--pipelinerun-file", "/workspace/pipelinerun.yaml",
                "--config-dir", "/workspace"
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                self.fail(
                    f"Podman timed out after 300s for '{pipelinerun_key}' with config '{config_key}'.\n"
                    f"  Command: {' '.join(cmd)}"
                )

            if result.returncode != 0:
                self.fail(
                    f"Mutation failed for '{pipelinerun_key}' with config '{config_key}':\n"
                    f"  stderr: {result.stderr}\n"
                    f"  stdout: {result.stdout}"
                )

            try:
                mutated = yaml.safe_load(result.stdout)
            except yaml.YAMLError as e:
                self.fail(f"Failed to parse mutated YAML: {e}\nOutput was: {result.stdout}")

            if not isinstance(mutated, dict):
                self.fail(
                    f"Expected YAML mapping from mutation, got {type(mutated).__name__}: {result.stdout!r}"
                )

            return mutated

    def validate_mutation_result(self, test_key: str, test_combination: TestCombination) -> None:
        """Validate mutation results for a single test combination."""
        with self.subTest(test=test_key):
            config_key = test_combination["config_key"]
            test_config = self.processed_configs[config_key]
            pipelinerun_key = test_combination["pipelinerun_key"]
            pipelinerun_data = PIPELINERUN_DEFINITIONS[pipelinerun_key]

            print(f"  Running '{test_key}': {pipelinerun_data['name']} with {CONFIG_COMBINATIONS[config_key]['name']}")

            mutated = self.run_mutation_test(test_combination)

            expected = pipelinerun_data["expected"]
            original_metadata = pipelinerun_data["pipelinerun"].get("metadata", {})
            original_annotations = original_metadata.get("annotations", {}) or {}
            original_labels = original_metadata.get("labels", {}) or {}

            annotations = mutated.get("metadata", {}).get("annotations", {}) or {}
            expected_annotations = expected["annotations"]
            expected_annotations_full = {**original_annotations, **expected_annotations}
            self.assertDictEqual(
                annotations,
                expected_annotations_full,
                f"Annotations mismatch for '{test_key}': expected {expected_annotations_full}, got {annotations}"
            )

            labels = mutated.get("metadata", {}).get("labels", {}) or {}
            expected_labels = expected["labels"]
            expected_labels_full = {**original_labels, **expected_labels}
            self.assertDictEqual(
                labels,
                expected_labels_full,
                f"Labels mismatch for '{test_key}': expected {expected_labels_full}, got {labels}"
            )

    def test_all_mutations(self):
        """Test all tekton-kueue mutation scenarios for available configs."""
        for test_key, test_combination in TEST_COMBINATIONS.items():
            if test_combination["config_key"] not in self.processed_configs:
                continue
            self.validate_mutation_result(test_key, test_combination)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test tekton-kueue CEL expressions")
    parser.add_argument("--check-setup", action="store_true",
                       help="Check if prerequisites are met and show configuration")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Run tests with verbose output")

    args, unknown = parser.parse_known_args()

    if args.check_setup:
        try:
            check_prerequisites(should_print=True)
        except Exception as e:
            print(f"✗ {e}")
            sys.exit(1)

        print("\n✅ All prerequisites met! Ready to run tests.")
        print("Run: python hack/test-tekton-kueue-config.py")

    else:
        verbosity = 2 if args.verbose else 1
        sys.argv = [sys.argv[0]] + unknown
        unittest.main(verbosity=verbosity)
