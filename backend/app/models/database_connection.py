"""MintHRM — DatabaseConnection and DataAccessRule SQLAlchemy models.

Ported directly from mint-analytics. Each tenant stores their own ad-hoc
connections in their mart schema (search_path handles isolation).
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.sql import func

from app.core.database import Base


class DatabaseConnection(Base):
    """Customer database connection with Fernet-encrypted credentials.

    Supports postgres, mysql, sqlserver.
    SSH tunnel fields allow routing through a bastion host.
    """

    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, index=True)

    # Display
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    engine = Column(String(50), nullable=False)  # postgres | mysql | sqlserver

    # Connection
    host = Column(String(500), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(Text, nullable=False)  # Fernet-encrypted

    # Optional
    default_schema = Column(String(255), nullable=True)
    ssl_mode = Column(String(50), nullable=True)
    connection_options = Column(JSON, default={})

    # SSH Tunnel — when ssh_enabled the backend opens an SSH port forward
    # to ssh_host:ssh_port and routes the DB connection through an ephemeral
    # local port. All credential fields are Fernet-encrypted.
    ssh_enabled = Column(Boolean, default=False, nullable=False)
    ssh_host = Column(String(500), nullable=True)
    ssh_port = Column(Integer, nullable=True)
    ssh_username = Column(String(255), nullable=True)
    ssh_auth_method = Column(String(20), nullable=True)   # "password" | "key"
    ssh_password_encrypted = Column(Text, nullable=True)
    ssh_private_key_encrypted = Column(Text, nullable=True)
    ssh_key_passphrase_encrypted = Column(Text, nullable=True)
    ssh_known_host_key = Column(Text, nullable=True)

    # Organisation
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=[])

    # Health
    is_healthy = Column(Boolean, default=True)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_check_error = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataAccessRule(Base):
    """Row-level security rule for a DatabaseConnection.

    When a connection has active rules, every query is rewritten to add a
    WHERE target_column IN (values_from_external_api) filter.
    """

    __tablename__ = "data_access_rules"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # What to filter
    target_column = Column(String(255), nullable=False)
    apply_to_tables = Column(JSON, default=[])   # ["*"] = all tables

    # External API that returns allowed values
    external_api_url = Column(Text, nullable=False)
    external_api_method = Column(String(10), default="POST")
    external_api_headers = Column(JSON, default={})
    external_api_body = Column(JSON, default={})
    response_values_path = Column(String(500), nullable=False)

    cache_ttl_seconds = Column(Integer, default=300)
    applies_to_roles = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
