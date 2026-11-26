# ADR 0029: External identity and secure sessions

Use validated OIDC JWTs (issuer, audience, signature, expiry, JWKS) in production. Keep
a signed, short-lived HttpOnly development session adapter for local/demo use. Do not
store passwords or provider tokens in the browser.
