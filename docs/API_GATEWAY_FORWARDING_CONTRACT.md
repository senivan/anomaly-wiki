# API Gateway Forwarding Contract

This document defines how `api-gateway` forwards authenticated requests to internal services.

## Scope

Applies to downstream HTTP calls from `api-gateway` to:

- `encyclopedia-service`
- `search-service`
- `media-service`

Public auth proxy routes to `researcher-auth-service` are out of scope for this contract because they forward client credentials directly and do not attach gateway-issued identity headers.

## Trust Boundary

`api-gateway` is responsible for validating external bearer tokens.

Downstream services must treat the following headers as trusted only when the request originates from `api-gateway` on an internal network boundary:

- `X-Authenticated-User-Id`
- `X-Authenticated-User-Email`
- `X-Authenticated-User-Role`
- `X-Authenticated-Source`

Downstream services must not accept those headers from public clients directly.

## Header Contract

For authenticated downstream requests, `api-gateway` forwards:

- `X-Authenticated-User-Id`: validated JWT `sub`
- `X-Authenticated-User-Email`: validated JWT `email`, if present
- `X-Authenticated-User-Role`: validated JWT `role`, if present
- `X-Authenticated-Source`: always `api-gateway`
- `X-Request-ID`: propagated request correlation ID

For protected forwarding, `api-gateway` strips any client-supplied versions of:

- `Authorization`
- `X-Authenticated-User-Id`
- `X-Authenticated-User-Email`
- `X-Authenticated-User-Role`
- `X-Authenticated-Source`

This prevents clients from spoofing internal identity context.

## Timeout And Retry Behavior

- Internal downstream calls use the gateway timeout configured by `API_GATEWAY_UPSTREAM_TIMEOUT_SECONDS`.
- The current implementation does not perform automatic retries.
- Non-idempotent requests must remain single-attempt to avoid duplicate writes.
- Timeout failures are normalized by the gateway into `504 upstream_timeout`.
- Connection failures are normalized by the gateway into `503 upstream_unavailable`.

If retries are introduced later, they should be limited to explicitly safe idempotent operations and documented per route.

## Downstream Expectations

Downstream services should:

- trust the forwarded identity headers only from `api-gateway`
- use `X-Authenticated-User-Id` as the stable caller identity
- use `X-Authenticated-User-Role` for coarse authorization context when needed
- keep service-specific business authorization in the downstream service, not in `api-gateway`
- log `X-Request-ID` for cross-service tracing

## Compatibility Notes

- This contract is additive to existing request payloads and query parameters.
- The gateway does not currently forward the raw bearer token to downstream services for protected internal calls.
- If a downstream service still requires raw JWT verification, that should be treated as a separate compatibility decision rather than implicit gateway behavior.
