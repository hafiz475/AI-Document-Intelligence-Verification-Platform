# ADR 0031: Private storage abstraction and Azure Blob

Keep document binaries behind `DocumentStorage`. Local storage is development/single-VM;
Azure Blob uses a private container, managed identity, server-side reads, and generated
project/document prefixes. Public object URLs are never exposed.
