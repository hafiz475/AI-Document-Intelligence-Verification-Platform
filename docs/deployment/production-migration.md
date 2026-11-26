# Azure production migration path

The portfolio demo remains a cost-conscious single VM: Nginx, FastAPI, React,
PostgreSQL, Redis, Dramatiq, and a private local volume. Only the web port is published.
It may remain raw HTTP and development-authenticated; that is not production HTTPS or
OIDC.

For production, terminate TLS and redirect HTTP at Azure Front Door/Application Gateway
or a managed application ingress; set the exact HTTPS frontend origin, secure cookies,
and HSTS. Configure an OIDC authorization-code/PKCE client and validated issuer,
audience, and JWKS. Run API/web/workers on Container Apps or App Service, use Azure
Database for PostgreSQL, Azure Managed Redis, private Azure Blob Storage, Key Vault,
managed identity, and Azure Monitor/Application Insights. Use private endpoints and
network rules so PostgreSQL, Redis, workers, metrics, and storage are not public.

Migration order: establish identity/networking; copy and verify blobs; migrate and
validate PostgreSQL; configure managed secrets; deploy workers/API/web; run isolation,
grounding, restore, and security acceptance; then switch DNS/TLS. Do not migrate solely
to make the demo appear more production-like.
