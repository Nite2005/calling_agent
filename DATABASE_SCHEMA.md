# Database Schema Documentation

## Overview

The AI SDR uses SQLite with SQLAlchemy ORM. All tables use UUID primary keys for distributed systems support.

---

## Table Structures

### agents

**Purpose:** Store AI agent configurations

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `agent_id` | String(100) | No | - | Unique identifier |
| `name` | String(255) | No | - | Display name |
| `system_prompt` | Text | No | - | AI system instruction |
| `first_message` | Text | Yes | NULL | Initial greeting |
| `voice_provider` | String(50) | No | "deepgram" | Voice service provider |
| `voice_id` | String(100) | No | "aura-2-thalia-en" | Voice identifier |
| `model_provider` | String(50) | No | "ollama" | LLM provider |
| `model_name` | String(100) | No | "mixtral:8x7b" | Model identifier |
| `interrupt_enabled` | Boolean | No | True | Allow user interruption |
| `silence_threshold_sec` | Float | No | 0.8 | Silence timeout |
| `created_at` | DateTime | No | now() | Creation timestamp |
| `updated_at` | DateTime | No | now() | Last update timestamp |
| `user_id` | String(100) | Yes | NULL | Multi-tenancy support |
| `is_active` | Boolean | No | True | Active status |

**Indexes:**
```sql
CREATE INDEX idx_user_id ON agents(user_id);
CREATE INDEX idx_is_active ON agents(is_active);
```

**SQL:**
```sql
CREATE TABLE agents (
    agent_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    system_prompt TEXT NOT NULL,
    first_message TEXT,
    voice_provider VARCHAR(50) DEFAULT 'deepgram',
    voice_id VARCHAR(100) DEFAULT 'aura-2-thalia-en',
    model_provider VARCHAR(50) DEFAULT 'ollama',
    model_name VARCHAR(100) DEFAULT 'mixtral:8x7b',
    interrupt_enabled BOOLEAN DEFAULT 1,
    silence_threshold_sec FLOAT DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100),
    is_active BOOLEAN DEFAULT 1
);
```

---

### conversations

**Purpose:** Store conversation history and metadata

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `conversation_id` | String(100) | No | - | Twilio call SID |
| `agent_id` | String(100) | No | - | Associated agent |
| `status` | String(50) | No | "in-progress" | Call status |
| `transcript` | Text | Yes | NULL | Full conversation text |
| `phone_number` | String(20) | Yes | NULL | Caller number |
| `started_at` | DateTime | Yes | NULL | Call start time |
| `ended_at` | DateTime | Yes | NULL | Call end time |
| `created_at` | DateTime | No | now() | Record creation time |

**Status Values:**
- `in-progress` - Call is active
- `completed` - Call ended normally
- `failed` - Call failed
- `disconnected` - User disconnected
- `timeout` - Call timeout

**Indexes:**
```sql
CREATE INDEX idx_agent_id ON conversations(agent_id);
CREATE INDEX idx_status ON conversations(status);
CREATE INDEX idx_started_at ON conversations(started_at);
```

**SQL:**
```sql
CREATE TABLE conversations (
    conversation_id VARCHAR(100) PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'in-progress',
    transcript TEXT,
    phone_number VARCHAR(20),
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);
```

---

### knowledge_bases

**Purpose:** Store uploaded documents for RAG

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `kb_id` | String(100) | No | - | Unique identifier |
| `agent_id` | String(100) | No | - | Associated agent |
| `name` | String(255) | No | - | Document name |
| `file_path` | String(500) | Yes | NULL | File location |
| `file_type` | String(50) | No | - | File type (pdf, txt, docx) |
| `chunk_count` | Integer | No | 0 | Number of chunks |
| `created_at` | DateTime | No | now() | Upload time |

**SQL:**
```sql
CREATE TABLE knowledge_bases (
    kb_id VARCHAR(100) PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_type VARCHAR(50) NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);
```

---

### agent_tools

**Purpose:** Store custom tools/actions for agents

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `tool_id` | String(100) | No | - | Unique identifier |
| `agent_id` | String(100) | No | - | Associated agent |
| `name` | String(100) | No | - | Tool name |
| `description` | Text | No | - | Tool description |
| `required_params` | String(1000) | No | "[]" | Required parameters (JSON) |
| `optional_params` | String(1000) | Yes | "[]" | Optional parameters (JSON) |
| `webhook_url` | String(500) | Yes | NULL | Webhook for execution |
| `created_at` | DateTime | No | now() | Creation time |

**SQL:**
```sql
CREATE TABLE agent_tools (
    tool_id VARCHAR(100) PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    required_params VARCHAR(1000) DEFAULT '[]',
    optional_params VARCHAR(1000) DEFAULT '[]',
    webhook_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);
```

---

### webhooks

**Purpose:** Store webhook configurations for events

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `webhook_id` | String(100) | No | - | Unique identifier |
| `agent_id` | String(100) | Yes | NULL | Associated agent |
| `url` | String(500) | No | - | Webhook URL |
| `events` | String(1000) | No | - | Event list (JSON) |
| `is_active` | Boolean | No | True | Active status |
| `created_at` | DateTime | No | now() | Creation time |

**SQL:**
```sql
CREATE TABLE webhooks (
    webhook_id VARCHAR(100) PRIMARY KEY,
    agent_id VARCHAR(100),
    url VARCHAR(500) NOT NULL,
    events VARCHAR(1000) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);
```

---

### phone_numbers

**Purpose:** Store Twilio phone numbers

**Fields:**
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `phone_id` | String(100) | No | - | Unique identifier |
| `phone_number` | String(20) | No | - | Phone number |
| `friendly_name` | String(255) | Yes | NULL | Display name |
| `agent_id` | String(100) | Yes | NULL | Associated agent |
| `type` | String(50) | No | "inbound" | Phone type |
| `is_active` | Boolean | No | True | Active status |
| `created_at` | DateTime | No | now() | Creation time |

**SQL:**
```sql
CREATE TABLE phone_numbers (
    phone_id VARCHAR(100) PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    friendly_name VARCHAR(255),
    agent_id VARCHAR(100),
    type VARCHAR(50) DEFAULT 'inbound',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);
```

---

## Relationships

```
agents (1) ──→ (N) conversations
          ├──→ (N) knowledge_bases
          ├──→ (N) agent_tools
          └──→ (N) phone_numbers

webhooks → (0..1) agents
```

---

## Common Queries

### Get Agent with All Data

```python
from models import Agent, SessionLocal
from sqlalchemy.orm import joinedload

db = SessionLocal()

agent = db.query(Agent).filter(
    Agent.agent_id == "agent_123"
).first()

# Access relationships
for tool in agent.tools:
    print(tool.name)

db.close()
```

### Get Active Conversations by Agent

```python
from models import Conversation, SessionLocal

db = SessionLocal()

convs = db.query(Conversation).filter(
    Conversation.agent_id == "agent_123",
    Conversation.status == "in-progress"
).all()

db.close()
```

### Get Conversation with Statistics

```python
from models import Conversation, SessionLocal
from sqlalchemy import func

db = SessionLocal()

# Get conversation count by status
stats = db.query(
    Conversation.status,
    func.count(Conversation.conversation_id).label('count')
).group_by(Conversation.status).all()

for status, count in stats:
    print(f"{status}: {count}")

db.close()
```

### Delete Old Conversations

```python
from models import Conversation, SessionLocal
from datetime import datetime, timedelta

db = SessionLocal()

# Delete conversations older than 30 days
cutoff = datetime.utcnow() - timedelta(days=30)

db.query(Conversation).filter(
    Conversation.created_at < cutoff
).delete()

db.commit()
db.close()
```

---

## Data Migration

### Add New Column

```python
# models.py
class Agent(Base):
    # ... existing fields ...
    new_field = Column(String(100), default="default_value")

# Then in database:
# ALTER TABLE agents ADD COLUMN new_field VARCHAR(100) DEFAULT 'default_value';
```

### Rename Column

```sql
-- SQLite doesn't support direct rename, use:
BEGIN TRANSACTION;

CREATE TABLE agents_new (
    -- Copy schema with new column name
);

INSERT INTO agents_new SELECT * FROM agents;

DROP TABLE agents;

ALTER TABLE agents_new RENAME TO agents;

COMMIT;
```

### Add Index

```sql
CREATE INDEX idx_agent_created_at ON agents(created_at);
```

---

## Backups

### Export to CSV

```python
import csv
from models import Agent, SessionLocal

db = SessionLocal()
agents = db.query(Agent).all()

with open("agents_backup.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["agent_id", "name", "model_name"])
    for agent in agents:
        writer.writerow([agent.agent_id, agent.name, agent.model_name])

db.close()
```

### Database Backup

```bash
# SQLite backup
sqlite3 agents.db ".dump" > backup.sql

# Or using Python
import sqlite3
import shutil

shutil.copy('agents.db', 'agents.db.backup')
```

---

## Performance Tuning

### Query Optimization

```python
# ✅ Load only needed columns
query = db.query(Agent.agent_id, Agent.name).all()

# ❌ Load entire object if not needed
query = db.query(Agent).all()
```

### Index Strategy

```python
class Agent(Base):
    __tablename__ = "agents"
    
    agent_id = Column(String, primary_key=True)
    name = Column(String, index=True)  # Add index for searches
    is_active = Column(Boolean, index=True)  # Index for filtering
    created_at = Column(DateTime, index=True)  # Index for time ranges
```

### Connection Pooling

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'sqlite:///agents.db',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

---

## Monitoring

### Database Size

```bash
ls -lh agents.db
sqlite3 agents.db "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();"
```

### Table Statistics

```sql
SELECT 
    name as table_name,
    SUM(pgsize) as size_bytes
FROM pragma_page_index_leaf_info('agents')
GROUP BY name;
```

---

**Last Updated:** January 2026
