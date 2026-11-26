# ADR 0030: Simple project RBAC

Persist OWNER, EDITOR, and VIEWER memberships and authorize every project route before
dispatch. OWNER administers membership/configuration; EDITOR mutates workflows; VIEWER
reads. Prevent removal or demotion of the final owner.
