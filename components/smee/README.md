# Smee component

The Smee component uses [gosmee][gs] in server mode and is deployed to the following clusters:
* external-production (kflux-c-prd-e01)
* external-staging (kflux-c-stg-e01)

This component uses webhooks to allow external SCM (source code management) tools to connect to internal RedHat resources; thus, the internal Konflux ROSA clusters provide a webhook forwarding service similar to [smee.io][sm]. Each Kustomize overlay includes an IP allow list patch with the NAT gateways of the allowed internal Konflux ROSA clusters.

[gs]: https://github.com/chmouel/gosmee
[sm]: https://smee.io/
