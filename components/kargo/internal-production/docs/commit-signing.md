# Commit signing

[Operations](operations.md) · [Kargo overview](../../README.md)

Kargo uses a GPG key to sign promotion commits locally. When publishing through
`github-push`, Kargo checks that signature and uses the configured GitHub App to
create the trusted commit on GitHub. GitHub signs that commit and attributes it
to the App.

The GPG signing key and the GitHub App credential have different purposes:

- **GPG key:** establishes trust in commits created by Kargo.
- **GitHub App credential:** authenticates Kargo to GitHub.

Changing the Git author name does not change which App publishes the commit.
See the [Kargo signing documentation](https://docs.kargo.io/user-guide/reference-docs/promotion-steps/github-push#trust-attribution-and-verification).

## What needs to be in Vault

The signing key must be supplied separately from the Git configuration.
Deploying the manifests does not create or upload it.

Each environment's configured Vault record needs a `signingKey` field containing
an unencrypted, ASCII-armored GPG private key. Its identity must match the name
and email configured in Kargo's `gitClient` settings.

External Secrets synchronizes the key into Kubernetes for the controllers and
shards. Check the relevant ExternalSecret manifest for the Vault path; updating
one environment does not update the other.

Preserve the exported key exactly, including the blank line after the PGP
header. Prefer uploading from a file rather than manually copying or editing
the key. Keep private keys out of Git, chat and logs.

## Updating the key

Update Vault when setting up signing, rotating the key, or replacing an expired,
damaged or exposed key:

1. Generate or obtain the replacement key and validate that it can sign.
2. Update the `signingKey` field in the relevant Vault record.
3. Confirm External Secrets has synchronized it to the controllers and shards
   that execute promotions.
4. Run a new promotion and check the resulting commit's attribution and
   verification on GitHub.

Existing published commits keep their GitHub signatures. If cloning fails with
a GPG import error, check the stored key's formatting and synchronization first.
