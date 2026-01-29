"""PostgreSQL MCP Server - A Model Context Protocol server for PostgreSQL databases."""

import asyncio
import os
import sys
from typing import Any, Optional

import psycopg
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

# Initialize FastMCP server
mcp = FastMCP(
    "postgresql-mcp-server",
    instructions="PostgreSQL database server. Use tools to query databases, list tables, and explore schemas.",
)


def get_connection_params() -> dict[str, Any]:
    """Get database connection parameters from environment variables."""
    return {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT", "5432")),
        "dbname": os.environ.get("PG_DATABASE", "postgres"),
        "user": os.environ.get("PG_USER", "postgres"),
        "password": os.environ.get("PG_PASSWORD", ""),
    }


def get_connection_string() -> str:
    """Build connection string from environment variables."""
    params = get_connection_params()
    return (
        f"postgresql://{params['user']}:{params['password']}"
        f"@{params['host']}:{params['port']}/{params['dbname']}"
    )


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


@mcp.tool(
    description="Test database connection and return server information",
    annotations=ToolAnnotations(title="Test Connection", readOnlyHint=True),
)
async def test_connection() -> str:
    """Test the database connection and return server version."""
    try:
        result = await execute_query("SELECT version() as version")
        if result:
            return f"Connected successfully!\nServer: {result[0]['version']}"
        return "Connected successfully!"
    except Exception as e:
        return f"Connection failed: {str(e)}"


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
    # Validate required environment variables
    required_vars = ["PG_HOST", "PG_DATABASE", "PG_USER"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(f"Warning: Missing environment variables: {', '.join(missing)}")
        print("Using defaults: localhost/postgres/postgres")

    # Windows event loop compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
