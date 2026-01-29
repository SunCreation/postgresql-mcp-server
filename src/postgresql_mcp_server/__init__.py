"""PostgreSQL MCP Server - A Model Context Protocol server for PostgreSQL databases."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import psycopg
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

# Config file path
CONFIG_DIR = Path.home() / ".config" / "postgresql-mcp"
CONFIG_FILE = CONFIG_DIR / "connections.json"

# Current active connection profile
_current_profile: Optional[str] = None
_connections: dict[str, dict[str, Any]] = {}

# Initialize FastMCP server
mcp = FastMCP(
    "postgresql-mcp-server",
    instructions="""PostgreSQL database server with multi-connection support.

FIRST TIME SETUP:
1. Use 'save_connection' to save your database credentials with a profile name
2. Use 'use_connection' to activate a profile
3. Then use other tools to query the database

MANAGING CONNECTIONS:
- save_connection: Save new DB credentials with a profile name
- list_connections: Show all saved connection profiles  
- use_connection: Switch to a specific profile
- delete_connection: Remove a saved profile
- get_current_connection: Show which profile is active

QUERYING:
- test_connection: Test if current connection works
- list_databases, list_schemas, list_tables: Explore DB structure
- describe_table: Get column details
- run_query: Execute SELECT queries
- run_sql: Execute any SQL (careful!)
""",
)


def load_connections() -> dict[str, dict[str, Any]]:
    """Load saved connections from config file."""
    global _connections
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                _connections = data.get("connections", {})
                return _connections
        except Exception:
            pass
    return {}


def save_connections() -> None:
    """Save connections to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"connections": _connections}, f, indent=2)
    # Secure the file (owner read/write only)
    os.chmod(CONFIG_FILE, 0o600)


def get_connection_params() -> dict[str, Any]:
    """Get database connection parameters from current profile or environment."""
    global _current_profile, _connections

    # First check if we have an active profile
    if _current_profile and _current_profile in _connections:
        conn = _connections[_current_profile]
        return {
            "host": conn.get("host", "localhost"),
            "port": int(conn.get("port", 5432)),
            "dbname": conn.get("database", "postgres"),
            "user": conn.get("user", "postgres"),
            "password": conn.get("password", ""),
        }

    # Fall back to environment variables
    return {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT", "5432")),
        "dbname": os.environ.get("PG_DATABASE", "postgres"),
        "user": os.environ.get("PG_USER", "postgres"),
        "password": os.environ.get("PG_PASSWORD", ""),
    }


async def execute_query(query: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
    """Execute a query and return results as a list of dictionaries."""
    conn_params = get_connection_params()
    async with await psycopg.AsyncConnection.connect(**conn_params) as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = await cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []


async def execute_command(query: str, params: Optional[tuple] = None) -> int:
    """Execute a command (INSERT, UPDATE, DELETE) and return affected row count."""
    conn_params = get_connection_params()
    async with await psycopg.AsyncConnection.connect(**conn_params) as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            await conn.commit()
            return cur.rowcount


# ============================================================
# CONNECTION MANAGEMENT TOOLS
# ============================================================


@mcp.tool(
    description="Save database connection credentials with a profile name. Credentials are stored securely in ~/.config/postgresql-mcp/connections.json",
    annotations=ToolAnnotations(title="Save Connection"),
)
def save_connection(
    profile_name: str = Field(
        description="Name for this connection profile (e.g., 'production', 'staging', 'local')"
    ),
    host: str = Field(description="Database host (e.g., 'localhost' or 'db.example.com')"),
    port: int = Field(description="Database port", default=5432),
    database: str = Field(description="Database name"),
    user: str = Field(description="Database username"),
    password: str = Field(description="Database password"),
) -> dict[str, Any]:
    """Save a new database connection profile."""
    global _connections, _current_profile

    load_connections()

    _connections[profile_name] = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
    }

    save_connections()

    # Auto-activate if this is the first connection
    if _current_profile is None:
        _current_profile = profile_name
        return {
            "status": "success",
            "message": f"Connection '{profile_name}' saved and activated!",
            "profile": profile_name,
            "host": host,
            "database": database,
            "config_path": str(CONFIG_FILE),
        }

    return {
        "status": "success",
        "message": f"Connection '{profile_name}' saved. Use 'use_connection' to activate it.",
        "profile": profile_name,
        "host": host,
        "database": database,
        "config_path": str(CONFIG_FILE),
    }


@mcp.tool(
    description="List all saved database connection profiles",
    annotations=ToolAnnotations(title="List Connections", readOnlyHint=True),
)
def list_connections() -> dict[str, Any]:
    """List all saved connection profiles."""
    global _current_profile

    load_connections()

    if not _connections:
        return {
            "status": "empty",
            "message": "No saved connections. Use 'save_connection' to add one.",
            "connections": [],
        }

    profiles = []
    for name, conn in _connections.items():
        profiles.append(
            {
                "name": name,
                "host": conn.get("host"),
                "port": conn.get("port"),
                "database": conn.get("database"),
                "user": conn.get("user"),
                "active": name == _current_profile,
            }
        )

    return {
        "status": "success",
        "current_profile": _current_profile,
        "connections": profiles,
        "config_path": str(CONFIG_FILE),
    }


@mcp.tool(
    description="Switch to a specific database connection profile",
    annotations=ToolAnnotations(title="Use Connection"),
)
def use_connection(
    profile_name: str = Field(description="Name of the connection profile to activate"),
) -> dict[str, Any]:
    """Activate a specific connection profile."""
    global _current_profile

    load_connections()

    if profile_name not in _connections:
        available = list(_connections.keys()) if _connections else []
        return {
            "status": "error",
            "message": f"Profile '{profile_name}' not found.",
            "available_profiles": available,
        }

    _current_profile = profile_name
    conn = _connections[profile_name]

    return {
        "status": "success",
        "message": f"Now using connection '{profile_name}'",
        "profile": profile_name,
        "host": conn.get("host"),
        "database": conn.get("database"),
    }


@mcp.tool(
    description="Delete a saved database connection profile",
    annotations=ToolAnnotations(title="Delete Connection"),
)
def delete_connection(
    profile_name: str = Field(description="Name of the connection profile to delete"),
) -> dict[str, Any]:
    """Delete a saved connection profile."""
    global _current_profile

    load_connections()

    if profile_name not in _connections:
        return {
            "status": "error",
            "message": f"Profile '{profile_name}' not found.",
        }

    del _connections[profile_name]
    save_connections()

    # If we deleted the active profile, clear it
    if _current_profile == profile_name:
        _current_profile = None
        # Auto-select another profile if available
        if _connections:
            _current_profile = list(_connections.keys())[0]

    return {
        "status": "success",
        "message": f"Profile '{profile_name}' deleted.",
        "new_active_profile": _current_profile,
    }


@mcp.tool(
    description="Show the currently active database connection",
    annotations=ToolAnnotations(title="Get Current Connection", readOnlyHint=True),
)
def get_current_connection() -> dict[str, Any]:
    """Get information about the current active connection."""
    global _current_profile

    load_connections()

    if _current_profile and _current_profile in _connections:
        conn = _connections[_current_profile]
        return {
            "status": "success",
            "profile": _current_profile,
            "host": conn.get("host"),
            "port": conn.get("port"),
            "database": conn.get("database"),
            "user": conn.get("user"),
            "source": "saved_profile",
        }

    # Using environment variables
    return {
        "status": "success",
        "profile": None,
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": os.environ.get("PG_PORT", "5432"),
        "database": os.environ.get("PG_DATABASE", "postgres"),
        "user": os.environ.get("PG_USER", "postgres"),
        "source": "environment_variables",
        "hint": "No saved profile active. Use 'save_connection' to save credentials.",
    }


# ============================================================
# DATABASE QUERY TOOLS
# ============================================================


@mcp.tool(
    description="Test database connection and return server information",
    annotations=ToolAnnotations(title="Test Connection", readOnlyHint=True),
)
async def test_connection() -> str:
    """Test the database connection and return server version."""
    try:
        result = await execute_query("SELECT version() as version")
        profile_info = f" (profile: {_current_profile})" if _current_profile else ""
        if result:
            return f"Connected successfully{profile_info}!\nServer: {result[0]['version']}"
        return f"Connected successfully{profile_info}!"
    except Exception as e:
        return f"Connection failed: {str(e)}\nHint: Use 'save_connection' to configure credentials or 'list_connections' to see available profiles."


@mcp.tool(
    description="List all databases in the PostgreSQL server",
    annotations=ToolAnnotations(title="List Databases", readOnlyHint=True),
)
async def list_databases() -> list[dict[str, Any]]:
    """List all databases in the server."""
    try:
        query = """
            SELECT 
                datname as database_name,
                pg_catalog.pg_get_userbyid(datdba) as owner,
                pg_catalog.pg_encoding_to_char(encoding) as encoding,
                datcollate as collation
            FROM pg_database
            WHERE datistemplate = false
            ORDER BY datname
        """
        return await execute_query(query)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="List all schemas in the current database",
    annotations=ToolAnnotations(title="List Schemas", readOnlyHint=True),
)
async def list_schemas() -> list[dict[str, Any]]:
    """List all schemas in the current database."""
    try:
        query = """
            SELECT 
                schema_name,
                schema_owner,
                CASE 
                    WHEN schema_name LIKE 'pg_%' THEN 'system'
                    WHEN schema_name = 'information_schema' THEN 'system'
                    ELSE 'user'
                END as schema_type
            FROM information_schema.schemata
            ORDER BY schema_type, schema_name
        """
        return await execute_query(query)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="List all tables in a schema (default: public)",
    annotations=ToolAnnotations(title="List Tables", readOnlyHint=True),
)
async def list_tables(
    schema_name: str = Field(description="Schema name to list tables from", default="public"),
) -> list[dict[str, Any]]:
    """List all tables in the specified schema."""
    try:
        query = """
            SELECT 
                table_name,
                table_type,
                pg_catalog.obj_description(
                    (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass, 
                    'pg_class'
                ) as description
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """
        return await execute_query(query, (schema_name,))
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="Get detailed column information for a table",
    annotations=ToolAnnotations(title="Describe Table", readOnlyHint=True),
)
async def describe_table(
    table_name: str = Field(description="Name of the table to describe"),
    schema_name: str = Field(description="Schema containing the table", default="public"),
) -> list[dict[str, Any]]:
    """Get column details for a specific table."""
    try:
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        return await execute_query(query, (schema_name, table_name))
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="Get indexes for a table",
    annotations=ToolAnnotations(title="Get Indexes", readOnlyHint=True),
)
async def get_indexes(
    table_name: str = Field(description="Name of the table"),
    schema_name: str = Field(description="Schema containing the table", default="public"),
) -> list[dict[str, Any]]:
    """Get all indexes for a specific table."""
    try:
        query = """
            SELECT 
                indexname as index_name,
                indexdef as index_definition
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            ORDER BY indexname
        """
        return await execute_query(query, (schema_name, table_name))
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="Get foreign key relationships for a table",
    annotations=ToolAnnotations(title="Get Foreign Keys", readOnlyHint=True),
)
async def get_foreign_keys(
    table_name: str = Field(description="Name of the table"),
    schema_name: str = Field(description="Schema containing the table", default="public"),
) -> list[dict[str, Any]]:
    """Get all foreign key relationships for a table."""
    try:
        query = """
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_schema AS foreign_schema,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
        """
        return await execute_query(query, (schema_name, table_name))
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="Execute a read-only SQL query (SELECT statements only)",
    annotations=ToolAnnotations(title="Run Query", readOnlyHint=True),
)
async def run_query(
    sql: str = Field(description="SQL SELECT query to execute"),
    limit: int = Field(description="Maximum number of rows to return", default=100),
) -> list[dict[str, Any]]:
    """Execute a read-only SQL query."""
    try:
        # Basic validation - only allow SELECT queries
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return [{"error": "Only SELECT queries are allowed. Use run_sql for other operations."}]

        # Add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = f"{sql.rstrip().rstrip(';')} LIMIT {limit}"

        return await execute_query(sql)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(
    description="Execute any SQL statement (INSERT, UPDATE, DELETE, CREATE, etc.) - USE WITH CAUTION",
    annotations=ToolAnnotations(title="Run SQL", destructiveHint=True),
)
async def run_sql(
    sql: str = Field(description="SQL statement to execute"),
) -> dict[str, Any]:
    """Execute any SQL statement. Use with caution as this can modify data."""
    try:
        sql_upper = sql.strip().upper()

        if sql_upper.startswith("SELECT"):
            results = await execute_query(sql)
            return {"type": "select", "rows": len(results), "data": results}
        else:
            affected = await execute_command(sql)
            return {"type": "command", "affected_rows": affected, "status": "success"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    description="Get table statistics including row count and size",
    annotations=ToolAnnotations(title="Table Stats", readOnlyHint=True),
)
async def get_table_stats(
    table_name: str = Field(description="Name of the table"),
    schema_name: str = Field(description="Schema containing the table", default="public"),
) -> dict[str, Any]:
    """Get statistics for a specific table."""
    try:
        query = """
            SELECT 
                pg_size_pretty(pg_total_relation_size(quote_ident(%s) || '.' || quote_ident(%s))) as total_size,
                pg_size_pretty(pg_relation_size(quote_ident(%s) || '.' || quote_ident(%s))) as table_size,
                pg_size_pretty(pg_indexes_size((quote_ident(%s) || '.' || quote_ident(%s))::regclass)) as index_size,
                (SELECT reltuples::bigint FROM pg_class 
                 WHERE oid = (quote_ident(%s) || '.' || quote_ident(%s))::regclass) as estimated_row_count
        """
        result = await execute_query(
            query,
            (
                schema_name,
                table_name,
                schema_name,
                table_name,
                schema_name,
                table_name,
                schema_name,
                table_name,
            ),
        )
        return result[0] if result else {"error": "Table not found"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    description="Search for tables, columns, or functions by name pattern",
    annotations=ToolAnnotations(title="Search Objects", readOnlyHint=True),
)
async def search_objects(
    pattern: str = Field(description="Search pattern (supports % wildcards)"),
    object_type: str = Field(
        description="Type of object to search: 'table', 'column', 'function', or 'all'",
        default="all",
    ),
) -> list[dict[str, Any]]:
    """Search for database objects by name pattern."""
    try:
        results = []
        pattern_lower = pattern.lower()

        if object_type in ("table", "all"):
            query = """
                SELECT 'table' as object_type, table_schema as schema, table_name as name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    AND LOWER(table_name) LIKE %s
                ORDER BY table_schema, table_name
            """
            results.extend(await execute_query(query, (pattern_lower,)))

        if object_type in ("column", "all"):
            query = """
                SELECT 'column' as object_type, 
                       table_schema || '.' || table_name as schema,
                       column_name as name,
                       data_type
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    AND LOWER(column_name) LIKE %s
                ORDER BY table_schema, table_name, column_name
            """
            results.extend(await execute_query(query, (pattern_lower,)))

        if object_type in ("function", "all"):
            query = """
                SELECT 'function' as object_type,
                       routine_schema as schema,
                       routine_name as name
                FROM information_schema.routines
                WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')
                    AND LOWER(routine_name) LIKE %s
                ORDER BY routine_schema, routine_name
            """
            results.extend(await execute_query(query, (pattern_lower,)))

        return results
    except Exception as e:
        return [{"error": str(e)}]


def main():
    """Main entry point for the MCP server."""
    # Load saved connections on startup
    load_connections()

    # Auto-select first profile if available and no env vars set
    global _current_profile
    if _connections and not os.environ.get("PG_HOST"):
        _current_profile = list(_connections.keys())[0]

    # Windows event loop compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
