# ADR 0032: Provider-neutral secrets and Key Vault

Resolve backend-only secret references through an environment adapter or Azure Key
Vault using managed identity. Persist references/status only and never return values.
