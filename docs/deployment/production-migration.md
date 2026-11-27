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

## Custom domain and HTTPS readiness checklist

1. Create a controlled DNS record for the chosen ingress and verify ownership before
   changing application origins.
2. Issue and bind a managed certificate at Front Door, Application Gateway, or the
   selected ingress. Keep automatic renewal enabled and alert on renewal failure or
   near-expiry; assign an emergency certificate replacement owner.
3. Redirect HTTP to HTTPS at ingress. Do not enable HSTS while users can still reach an
   HTTP-only endpoint.
4. Set `ASSUREAI_CORS_ORIGINS` to exact HTTPS origins and `VITE_API_BASE_URL` to the final
   HTTPS API URL. Remove raw-IP and development origins from production.
5. Enable secure, HttpOnly, SameSite-appropriate cookies only after end-to-end HTTPS is
   verified. Then introduce HSTS conservatively after rollback and subdomain tests.
6. Verify `/health`, `/ready`, OIDC callbacks, uploads, security headers, and mixed-content
   behavior through the custom domain.
7. Keep the raw-IP demo documented as HTTP until actually protected. A DNS record or open
   port 443 alone does not prove HTTPS is active.
