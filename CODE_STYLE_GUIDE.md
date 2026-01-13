# Code Style Guide & Best Practices

## Python Style (PEP 8)

### Naming Conventions

```python
# ✅ Classes: PascalCase
class ConnectionManager:
    pass

# ✅ Functions/Variables: snake_case
async def process_streaming_transcript():
    user_input = "hello"

# ✅ Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT_SEC = 30

# ❌ Avoid
class connection_manager:
    pass

def ProcessStreamingTranscript():
    UserInput = "hello"
```

### Type Hints

```python
# ✅ Always use type hints
async def query_rag_streaming(
    text: str,
    history: List[Dict[str, str]],
    call_sid: str
) -> AsyncIterator[str]:
    """Generate streaming response with RAG."""
    pass

# ✅ Optional types
def get_agent(agent_id: str) -> Optional[Agent]:
    pass

# ✅ Complex types
def process_calls(
    calls: Dict[str, WSConn],
    config: Dict[str, Any]
) -> None:
    pass

# ❌ Avoid
def query_rag_streaming(text, history, call_sid):
    pass
```

### Docstrings

```python
# ✅ Google style docstrings
async def handle_interrupt(call_sid: str) -> None:
    """Handle user interruption with seamless transition.
    
    Stops agent speaking, clears TTS queue, and resets
    speech detection for fresh input.
    
    Args:
        call_sid: Twilio call SID
        
    Returns:
        None
        
    Raises:
        ValueError: If call_sid is invalid
    """
    pass

# ✅ Concise for simple functions
def get_basename(path: str) -> str:
    """Extract filename from path."""
    return os.path.basename(path)

# ❌ Avoid
def handle_interrupt(call_sid):
    # Stop speaking
    # Clear queue
    pass
```

### Imports

```python
# ✅ Organize imports
import os
import asyncio
import time
from typing import Dict, Optional, List

from fastapi import FastAPI, WebSocket
from sqlalchemy.orm import Session

from models import Agent
from utils import _logger

# ❌ Avoid
from utils import *
import *
# Mixed order
from models import Agent
import os
from fastapi import FastAPI
from typing import Dict
```

### Line Length

```python
# ✅ Keep under 100 characters
response = await handle_user_input(
    text=text,
    call_sid=call_sid,
    agent_config=conn.agent_config
)

# ❌ Avoid
response = await handle_user_input(text=text, call_sid=call_sid, agent_config=conn.agent_config)
```

---

## Async/Await Best Practices

### Proper Async Usage

```python
# ✅ Use async for I/O operations
async def fetch_agent(agent_id: str) -> Agent:
    db = SessionLocal()
    agent = db.query(Agent).filter(
        Agent.agent_id == agent_id
    ).first()
    db.close()
    return agent

# ✅ Concurrent operations
tasks = [
    process_call(call_id)
    for call_id in call_ids
]
results = await asyncio.gather(*tasks)

# ❌ Don't block event loop
def blocking_operation():
    time.sleep(1)  # BAD!

# ✅ Do this instead
await asyncio.sleep(1)  # GOOD!
```

### Exception Handling

```python
# ✅ Specific exceptions
try:
    agent = db.query(Agent).filter(...).first()
except SQLAlchemyError as e:
    _logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500)

# ❌ Avoid broad catches
try:
    agent = db.query(Agent).filter(...).first()
except Exception:
    pass  # Silencing errors is bad
```

---

## FastAPI Best Practices

### Endpoint Structure

```python
# ✅ Well-organized endpoint
@app.post("/v1/convai/agents")
async def create_agent(
    agent: AgentCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Create a new agent.
    
    Args:
        agent: Agent configuration
        db: Database session
        api_key: API key for authentication
        
    Returns:
        Created agent data
        
    Raises:
        HTTPException: If agent already exists
    """
    try:
        if db.query(Agent).filter(...).first():
            raise HTTPException(
                status_code=400,
                detail="Agent already exists"
            )
        
        new_agent = Agent(**agent.dict())
        db.add(new_agent)
        db.commit()
        db.refresh(new_agent)
        
        return new_agent.__dict__
        
    except Exception as e:
        db.rollback()
        _logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
```

### Response Models

```python
# ✅ Use Pydantic models
class AgentResponse(BaseModel):
    agent_id: str
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentResponse:
    pass

# ❌ Avoid returning raw dicts
@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    pass
```

---

## SQLAlchemy Best Practices

### Query Writing

```python
# ✅ Use query objects
agents = db.query(Agent).filter(
    Agent.is_active == True
).order_by(Agent.created_at.desc()).all()

# ✅ Use exists() for checks
has_agent = db.query(
    db.query(Agent).filter(
        Agent.agent_id == "123"
    ).exists()
).scalar()

# ❌ Avoid multiple queries
agents = db.query(Agent).all()
for agent in agents:
    if agent.is_active:  # N+1 query!
        process(agent)

# ✅ Do this instead
agents = db.query(Agent).filter(Agent.is_active == True).all()
```

### Connection Management

```python
# ✅ Proper session handling
db = SessionLocal()
try:
    agent = db.query(Agent).filter(...).first()
    db.commit()
except Exception as e:
    db.rollback()
    raise
finally:
    db.close()

# ✅ Or use context manager
with SessionLocal() as db:
    agent = db.query(Agent).filter(...).first()
    db.commit()
```

---

## Error Handling

### Logging Standards

```python
# ✅ Appropriate log levels
_logger.debug("Detailed diagnostic info")
_logger.info("General informational message")
_logger.warning("Warning about potential issue")
_logger.error("Error occurred, but continuing")
_logger.critical("Fatal error, must stop")

# ✅ Include context
_logger.error(f"Failed to process call {call_sid}: {error}")

# ✅ Use exc_info for tracebacks
try:
    result = risky_operation()
except Exception as e:
    _logger.error("Operation failed", exc_info=True)
```

### Custom Exceptions

```python
# ✅ Define custom exceptions
class AgentNotFound(Exception):
    """Agent with given ID not found."""
    pass

class InvalidConfiguration(Exception):
    """Agent configuration is invalid."""
    pass

# ✅ Use them
try:
    agent = get_agent("nonexistent")
except AgentNotFound:
    _logger.warning("Agent not found")
    raise HTTPException(status_code=404)
```

---

## Testing Standards

### Unit Test Structure

```python
import pytest
from fastapi.testclient import TestClient

class TestAgentAPI:
    """Tests for agent management API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_agent(self):
        """Create sample agent data."""
        return {
            "name": "Test Agent",
            "system_prompt": "You are helpful"
        }
    
    def test_create_agent(self, client, sample_agent):
        """Test agent creation."""
        response = client.post("/agents", json=sample_agent)
        assert response.status_code == 200
        assert response.json()["name"] == sample_agent["name"]
    
    def test_get_nonexistent_agent(self, client):
        """Test getting non-existent agent."""
        response = client.get("/agents/nonexistent")
        assert response.status_code == 404
```

---

## Performance Best Practices

### Caching

```python
# ✅ Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_agent_config(agent_id: str) -> Dict:
    """Cache agent configs."""
    db = SessionLocal()
    agent = db.query(Agent).filter(...).first()
    db.close()
    return agent.config_dict

# ✅ Time-based cache
CACHE_EXPIRY = {}
CACHE_DURATION = 300  # 5 minutes

def get_cached(key: str, func, *args):
    """Get cached value or compute."""
    now = time.time()
    if key in CACHE_EXPIRY:
        if now - CACHE_EXPIRY[key] < CACHE_DURATION:
            return CACHE[key]
    
    result = func(*args)
    CACHE[key] = result
    CACHE_EXPIRY[key] = now
    return result
```

### Memory Management

```python
# ✅ Clean up resources
async def process_call(call_sid: str):
    try:
        conn = manager.get(call_sid)
        # ... process ...
    finally:
        await manager.disconnect(call_sid)

# ✅ Clear buffers
conn.stt_transcript_buffer = ""
conn.conversation_history = []
```

---

## Security Best Practices

### Input Validation

```python
# ✅ Validate all inputs
@app.post("/agents")
async def create_agent(agent: AgentCreate):
    """Validate input."""
    if not agent.name or len(agent.name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Invalid name")
    
    if len(agent.system_prompt) > 5000:
        raise HTTPException(
            status_code=400,
            detail="Prompt too long"
        )

# ✅ Use Pydantic validators
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = Field(..., max_length=5000)
```

### API Key Management

```python
# ✅ Never log keys
def verify_api_key(api_key: str) -> str:
    if api_key not in API_KEYS:
        _logger.warning("Invalid API key attempt")  # Don't log the key!
        raise HTTPException(status_code=401)
    return api_key

# ✅ Use environment variables
API_KEYS = os.getenv("API_KEYS", "").split(",")
JWT_SECRET = os.getenv("JWT_SECRET")
```

---

## Code Review Checklist

- [ ] Type hints on all functions
- [ ] Docstrings on public functions
- [ ] Error handling with try/except
- [ ] Proper logging at all levels
- [ ] No hardcoded secrets
- [ ] No broad Exception catches
- [ ] Async/await used correctly
- [ ] Database connections closed
- [ ] Resource cleanup (finally blocks)
- [ ] Tests written and passing
- [ ] No commented-out code
- [ ] Variable names are clear
- [ ] Line length < 100 characters
- [ ] Imports organized and sorted
- [ ] No duplicated code

---

## Common Mistakes to Avoid

| ❌ Wrong | ✅ Right |
|---------|----------|
| `try: ... except:` | `try: ... except SpecificError:` |
| `if x is True:` | `if x:` |
| `dict.keys()` in condition | `dict` in condition |
| `len(x) == 0` | `not x` |
| `async def` without await | Use `def` for sync functions |
| Global mutable state | Pass as function argument |
| Print for logging | Use `_logger` |
| Catch all exceptions | Catch specific ones |
| `*args` for everything | Use explicit parameters |
| No validation | Validate all inputs |

---

## Pre-commit Checklist

```bash
# 1. Run tests
pytest tests/ -v

# 2. Check formatting
black --check *.py

# 3. Lint
pylint *.py
flake8 *.py

# 4. Type checking
mypy *.py

# 5. Security check
bandit *.py
```

Setup pre-commit hook:
```bash
echo '#!/bin/bash
pytest tests/ || exit 1
flake8 *.py || exit 1
' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

**Last Updated:** January 2026
