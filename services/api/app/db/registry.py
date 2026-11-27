"""Import every model module so Alembic autogenerate and tests see the full metadata."""

from app.db.base import Base
from app.modules.audit import models as audit_models
from app.modules.documents import models as document_models
from app.modules.tenants import models as tenant_models

__all__ = ["Base", "audit_models", "document_models", "tenant_models"]
