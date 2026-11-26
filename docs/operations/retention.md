# Retention and deletion

No category is silently deleted. Operators define and approve retention periods for
original documents, chunks/vectors, extraction/evidence/review history, questions,
answers/citations, evaluation runs/results, and audit logs according to contract and
regulatory obligations.

Project deletion is OWNER-only and deletes private objects before cascading database
rows. A failure stops the operation so orphaned objects are not knowingly left behind.
Export required audit evidence before deletion; the current single-database schema
cascades project audit events. Document deletion is OWNER/EDITOR-authorized but blocked
when immutable extraction or RAG provenance exists. Documents without such history
delete the private object and cascade derived rows. There is no background retention
purge in M6.
