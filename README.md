# PostgreSQL MCP Server

A Model Context Protocol (MCP) server for PostgreSQL databases with **multi-connection profile management**.

## Features

- **Multi-Connection Profiles**: Save and switch between multiple database connections
- **Secure Credential Storage**: Credentials stored in `~/.config/postgresql-mcp/connections.json` with restricted permissions
- **Schema Exploration**: List databases, schemas, tables, columns
- **Query Execution**: Run SELECT queries (read-only) or any SQL (with caution)
- **Table Statistics**: Get row counts, sizes, and more

## Installation

### Using uvx (Recommended)

```bash
uvx --from git+https://github.com/SunCreation/postgresql-mcp-server postgresql-mcp-server
```

## Quick Start

Once the MCP server is running, use these tools in conversation:

### 1. First Time Setup
```
Save my database connection:
- Profile name: production
- Host: db.example.com
- Port: 5432
- Database: myapp
- User: admin
- Password: secretpass
```

### 2. Managing Multiple Connections
```
# List all saved connections
"Show me my saved database connections"

# Switch to a different profile
"Switch to the staging database"

# Delete a profile
"Delete the old-dev connection"
```

### 3. Querying
```
# After connection is set up
"List all tables"
"Describe the users table"
"Run query: SELECT * FROM orders LIMIT 10"
```

## OpenCode Configuration

Add to your `opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "postgresql": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/SunCreation/postgresql-mcp-server", "postgresql-mcp-server"],
      "enabled": true
    }
  }
}
```

**No environment variables needed!** Credentials are managed through conversation and stored securely.

## Available Tools

### Connection Management

| Tool | Description |
|------|-------------|
| `save_connection` | Save new DB credentials with a profile name |
| `list_connections` | Show all saved connection profiles |
| `use_connection` | Switch to a specific profile |
| `delete_connection` | Remove a saved profile |
| `get_current_connection` | Show which profile is active |

### Database Operations

| Tool | Description |
|------|-------------|
| `test_connection` | Test if current connection works |
| `list_databases` | List all databases |
| `list_schemas` | List all schemas |
| `list_tables` | List tables in a schema |
| `describe_table` | Get column details |
| `get_indexes` | Get table indexes |
| `get_foreign_keys` | Get FK relationships |
| `run_query` | Execute SELECT queries (read-only) |
| `run_sql` | Execute any SQL (careful!) |
| `get_table_stats` | Get table statistics |
| `search_objects` | Search for tables/columns/functions |

## Credential Storage

Credentials are stored in:
```
~/.config/postgresql-mcp/connections.json
```

The file has restricted permissions (600) so only you can read it.

Example structure:
```json
{
  "connections": {
    "production": {
      "host": "db.example.com",
      "port": 5432,
      "database": "myapp",
      "user": "admin",
      "password": "***"
    },
    "staging": {
      "host": "staging-db.example.com",
      "port": 5432,
      "database": "myapp_staging",
      "user": "dev",
      "password": "***"
    }
  }
}
```

## Security Considerations

- Credentials are stored with file permissions `600` (owner read/write only)
- Use read-only database users when possible
- `run_sql` can execute any SQL - use with caution
- Never share your `connections.json` file

## License

MIT License
