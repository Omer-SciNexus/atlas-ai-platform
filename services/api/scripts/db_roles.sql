-- Local/test database bootstrap. Runs once as the owner/superuser (POSTGRES_USER = atlas).
-- In cloud environments these roles are created by Terraform with secrets from the vault.
--
-- atlas      owns the schema and runs migrations.
-- atlas_app  is what the API connects as: not the owner, NOBYPASSRLS, so every query is
--            filtered by row-level security.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_app') THEN
        CREATE ROLE atlas_app LOGIN PASSWORD 'atlas_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE atlas TO atlas_app;
GRANT USAGE ON SCHEMA public TO atlas_app;

-- Tables the owner creates later are usable by the app role automatically.
ALTER DEFAULT PRIVILEGES FOR ROLE atlas IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO atlas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE atlas IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO atlas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE atlas IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO atlas_app;
