# Nimbus Labs Incident Runbook

Use this runbook when something breaks in production. As described in Section 2, every
incident gets a severity first. Refer to the Security Policy (SEC-104) for security incidents.

## 1. Escalation

Escalation goes from the on-call engineer to the owning team lead, and then to the incident
commander. The incident commander depends on the team lead for technical decisions.

## 2. Severity levels

| Severity | Meaning | Response time |
|---|---|---|
| SEV1 | customers cannot pay or sign in | 15 minutes |
| SEV2 | a major feature is degraded | 30 minutes |
| SEV3 | a minor feature is broken | 4 hours |
| SEV4 | a cosmetic or internal issue | next business day |

A SEV1 incident means customers cannot pay or sign in, and the on-call engineer must respond within 15 minutes.

A SEV2 incident means a major feature is degraded, and the on-call engineer must respond within 30 minutes.

A SEV3 incident means a minor feature is broken, and the on-call engineer must respond within 4 hours.

A SEV4 incident means a cosmetic or internal issue, and the on-call engineer must respond within next business day.

## INC-2041: Ledger unavailable

Incident INC-2041 affects the Ledger. The usual cause is that a Postgres Cluster failover left the Ledger connected to a read-only replica. To fix it, restart the Ledger connection pool so it reconnects to the new primary. Page the Payments team in #payments-oncall; see the Ledger section of the architecture document for the services it depends on.
## INC-2077: Token signing failures

Incident INC-2077 affects the Token Vault. The usual cause is that a signing key expired before rotation finished. To fix it, trigger a manual key rotation in the Token Vault. Page the Security Engineering team in #security; see the Token Vault section of the architecture document for the services it depends on.
