# Smee component

The Smee component uses [gosmee][gs] in server mode and is deployed to the following clusters:
* ext-prod (kflux-c-prd-e01)
* ext-stage (kflux-c-stg-e01)

as it allows external clusters to connect to internal RedHat resources. This allows the clusters to provide a webhook forwarding service similar to
[smee.io][sm].

[gs]: https://github.com/chmouel/gosmee
[sm]: https://smee.io/
