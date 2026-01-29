# PostgreSQL MCP Server

A Model Context Protocol (MCP) server for PostgreSQL databases. Allows AI agents to query databases, list tables, explore schemas, and execute SQL.

## Features

- **Connection Testing**: Verify database connectivity
- **Schema Exploration**: List databases, schemas, tables, columns
- **Index Information**: View table indexes and foreign keys
- **Query Execution**: Run SELECT queries (read-only) or any SQL (with caution)
- **Table Statistics**: Get row counts, sizes, and more
- **Object Search**: Find tables, columns, or functions by name pattern

## Installation

### Using uvx (Recommended)

```bash
uvx postgresql-mcp-server
```

### Using pip

```bash
pip install postgresql-mcp-server
```

## Environment Variables

The server requires the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PG_HOST` | PostgreSQL host | `localhost` |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DATABASE` | Database name | `postgres` |
| `PG_USER` | Database username | `postgres` |
| `PG_PASSWORD` | Database password | (empty) |

## OpenCode Configuration

Add the following to your `opencode.json` or `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "postgresql": {
      "type": "local",
      "command": ["uvx", "postgresql-mcp-server"],
      "enabled": true,
      "environment": {
        "PG_HOST": "your-database-host.com",
        "PG_PORT": "5432",
        "PG_DATABASE": "your_database",
        "PG_USER": "your_username",
        "PG_PASSWORD": "your_password"
      }
    }
  }
}
```

### Using with GitHub Package

If you've published to GitHub, you can use:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "postgresql": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/suncreation/postgresql-mcp-server", "postgresql-mcp-server"],
      "enabled": true,
      "environment": {
        "PG_HOST": "localhost",
        "PG_PORT": "5432",
        "PG_DATABASE": "mydb",
        "PG_USER": "myuser",
        "PG_PASSWORD": "mypassword"
      }
    }
  }
}
```

## Available Tools

### Connection & Info

- **test_connection**: Test database connection and return server version
- **list_databases**: List all databases in the PostgreSQL server
- **list_schemas**: List all schemas in the current database

### Table Operations

- **list_tables**: List all tables in a schema
- **describe_table**: Get detailed column information for a table
- **get_indexes**: Get indexes for a table
- **get_foreign_keys**: Get foreign key relationships for a table
- **get_table_stats**: Get table statistics (row count, size)

### Query Execution

- **run_query**: Execute a read-only SQL query (SELECT only)
- **run_sql**: Execute any SQL statement (USE WITH CAUTION)

### Search

- **search_objects**: Search for tables, columns, or functions by name pattern

## Usage Examples

Once configured in OpenCode, you can ask the AI:

- "Show me all tables in the public schema"
- "Describe the users table"
- "Run a query to get the top 10 orders"
- "What indexes exist on the products table?"
- "Search for columns containing 'email'"

## Security Considerations

- **run_sql** can execute any SQL including INSERT, UPDATE, DELETE, DROP. Use with caution.
- Consider using a read-only database user for safer operations.
- Never expose database credentials in public repositories.

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/suncreation/postgresql-mcp-server.git
cd postgresql-mcp-server

# Install dependencies
uv sync

# Run locally
uv run postgresql-mcp-server
```

### Testing

```bash
# Set environment variables
export PG_HOST=localhost
export PG_DATABASE=testdb
export PG_USER=testuser
export PG_PASSWORD=testpass

# Run the server
uv run postgresql-mcp-server
```

## License

MIT License - see LICENSE file for details.
