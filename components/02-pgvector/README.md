# 02 — pgvector (PostgreSQL)

Single PostgreSQL instance with pgvector extension hosting `llamastack`, `userinfo`, and the bootstrap DB. Post-deploy Job **`db-init`** runs all DDL and userinfo seeding in one Kubernetes Job.

See [full documentation](../../docs/components/02-pgvector.md).
