#!/usr/bin/env python3
"""
Test script for Documentation Chunking Strategy

Tests the specialized chunking strategy designed for package documentation.
Validates:
- Token counting
- Markdown structure parsing
- Header hierarchy analysis
- Smart chunk merging
- Oversized chunk splitting
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from webnexus.utils.documentation_chunking import DocumentationChunker
from webnexus.utils.token_counter import TokenCounter
from webnexus.utils.markdown_parser import MarkdownParser
from webnexus.utils.header_hierarchy import create_hierarchy_analyzer

# Sample documentation content (typical package documentation structure)
SAMPLE_DOCUMENTATION = """# FastAPI Documentation

FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.7+ based on standard Python type hints.

## Features

FastAPI provides several key features:

- **Fast**: Very high performance, on par with NodeJS and Go (thanks to Starlette and Pydantic)
- **Fast to code**: Increase the speed to develop features by about 200% to 300%
- **Fewer bugs**: Reduce about 40% of human (developer) induced errors
- **Intuitive**: Great editor support with completion everywhere
- **Easy**: Designed to be easy to use and learn
- **Short**: Minimize code duplication

## Installation

Install FastAPI using pip:

```bash
pip install fastapi
pip install "uvicorn[standard]"
```

You can also install with optional dependencies:

```bash
pip install "fastapi[all]"
```

## Quick Start

### Basic Example

Here's a minimal FastAPI application:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
```

Run the server:

```bash
uvicorn main:app --reload
```

### Path Parameters

Path parameters are declared in the function parameters:

```python
@app.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}
```

FastAPI provides automatic validation and conversion for path parameters.

### Query Parameters

Query parameters are function parameters that aren't part of the path:

```python
from typing import Optional

@app.get("/items/")
async def read_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}
```

Optional query parameters:

```python
@app.get("/items/{item_id}")
async def read_item(item_id: str, q: Optional[str] = None):
    if q:
        return {"item_id": item_id, "q": q}
    return {"item_id": item_id}
```

## Request Body

### Pydantic Models

Use Pydantic models to declare request bodies:

```python
from pydantic import BaseModel
from typing import Optional

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

@app.post("/items/")
async def create_item(item: Item):
    return item
```

### Nested Models

Pydantic supports nested models:

```python
class Image(BaseModel):
    url: str
    name: str

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    images: Optional[List[Image]] = None

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    return {"item_id": item_id, **item.dict()}
```

## Response Models

### Basic Response Model

Declare the response model using `response_model`:

```python
from pydantic import BaseModel, EmailStr

class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr

class UserOut(BaseModel):
    username: str
    email: EmailStr

@app.post("/users/", response_model=UserOut)
async def create_user(user: UserIn):
    return user
```

The response model ensures sensitive fields like passwords aren't included in the response.

### Response Model List

Return a list of items:

```python
@app.get("/items/", response_model=List[Item])
async def read_items():
    return [
        {"name": "Foo", "price": 50.2},
        {"name": "Bar", "price": 62.0}
    ]
```

## Dependency Injection

### Basic Dependencies

FastAPI provides a powerful dependency injection system:

```python
from fastapi import Depends

async def common_parameters(q: str = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}

@app.get("/items/")
async def read_items(commons: dict = Depends(common_parameters)):
    return commons
```

### Class Dependencies

Use classes as dependencies:

```python
class CommonQueryParams:
    def __init__(self, q: str = None, skip: int = 0, limit: int = 100):
        self.q = q
        self.skip = skip
        self.limit = limit

@app.get("/items/")
async def read_items(commons: CommonQueryParams = Depends()):
    return commons
```

## Security

### OAuth2 with Password Flow

Implement OAuth2 authentication:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

### JWT Tokens

Use JWT for secure authentication:

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```

## Testing

### Testing with TestClient

FastAPI provides a TestClient based on requests:

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

### Async Testing

For async tests, use httpx:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
```

## Advanced Features

### Background Tasks

Run tasks in the background:

```python
from fastapi import BackgroundTasks

def write_log(message: str):
    with open("log.txt", "a") as log:
        log.write(message)

@app.post("/send-notification/")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_log, f"Notification sent to {email}")
    return {"message": "Notification sent"}
```

### WebSocket Support

FastAPI supports WebSockets:

```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

### CORS Configuration

Enable CORS for your API:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI Schema**: Available at `/openapi.json`

### Customizing Documentation

Customize the documentation:

```python
app = FastAPI(
    title="My API",
    description="This is my awesome API",
    version="1.0.0",
    docs_url="/documentation",
    redoc_url="/redoc"
)
```

## Performance Tips

### Use Async/Await

For I/O-bound operations, use async/await:

- Database queries
- External API calls
- File operations

### Caching

Implement caching for expensive operations:

```python
from functools import lru_cache

@lru_cache()
def get_settings():
    return Settings()
```

### Database Connection Pooling

Use connection pooling for database operations:

```python
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

## Deployment

### Production Server

Use Gunicorn with Uvicorn workers:

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker Deployment

Create a Dockerfile:

```dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Use environment variables for configuration:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    app_name: str = "FastAPI"
    admin_email: str
    items_per_user: int = 50

    class Config:
        env_file = ".env"
```

## Best Practices

### Project Structure

Organize your project:

```
myproject/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── dependencies.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── items.py
│   │   └── users.py
│   └── internal/
│       ├── __init__.py
│       └── admin.py
└── tests/
    ├── __init__.py
    └── test_main.py
```

### Error Handling

Implement proper error handling:

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]
```

### Validation

Use Pydantic for comprehensive validation:

```python
from pydantic import BaseModel, Field, validator

class Item(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name must not be empty')
        return v
```

## Conclusion

FastAPI is a powerful framework that combines ease of use with high performance. Its automatic documentation, type checking, and modern Python features make it an excellent choice for building APIs.

For more information, visit the official documentation at https://fastapi.tiangolo.com
"""


def print_separator(title: str = ""):
    """Print a visual separator"""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")
    else:
        print(f"\n{'-' * 80}\n")


def test_token_counter():
    """Test token counting"""
    print_separator("Testing Token Counter")

    counter = TokenCounter()

    test_texts = [
        "Hello, World!",
        "FastAPI is a modern web framework for building APIs.",
        SAMPLE_DOCUMENTATION[:500]
    ]

    for i, text in enumerate(test_texts, 1):
        tokens = counter.count_tokens(text)
        words = len(text.split())
        chars = len(text)

        print(f"Text {i}:")
        print(f"  Characters: {chars}")
        print(f"  Words: {words}")
        print(f"  Tokens: {tokens}")
        print(f"  Encoding: {counter.get_encoding_name()}")
        print()


def test_markdown_parser():
    """Test markdown structure parsing"""
    print_separator("Testing Markdown Parser")

    parser = MarkdownParser()
    elements = parser.parse(SAMPLE_DOCUMENTATION)

    print(f"Total elements parsed: {len(elements)}")
    print()

    # Count element types
    type_counts = {}
    for elem in elements:
        type_name = elem.type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    print("Element type distribution:")
    for elem_type, count in sorted(type_counts.items()):
        print(f"  {elem_type}: {count}")

    print()

    # Show headers
    headers = [e for e in elements if e.type.value == "header"]
    print(f"Headers found: {len(headers)}")
    for header in headers[:10]:  # Show first 10
        level = header.level
        title = header.metadata.get("title", "")
        print(f"  {'  ' * (level - 1)}H{level}: {title}")

    print()

    # Show code blocks
    code_blocks = [e for e in elements if e.type.value == "code_block"]
    print(f"Code blocks found: {len(code_blocks)}")
    for i, cb in enumerate(code_blocks[:3], 1):  # Show first 3
        language = cb.metadata.get("language", "text")
        lines = cb.content.count('\n')
        print(f"  Code block {i}: {language} ({lines} lines)")

    print()


def test_header_hierarchy():
    """Test header hierarchy analysis"""
    print_separator("Testing Header Hierarchy")

    parser = MarkdownParser()
    elements = parser.parse(SAMPLE_DOCUMENTATION)

    analyzer = create_hierarchy_analyzer(elements)

    print(f"Total headers: {len(analyzer.get_all_headers())}")
    print()

    print("Header hierarchy:")
    analyzer.print_hierarchy()
    print()

    # Test hierarchy relationships
    headers = analyzer.get_all_headers()
    if len(headers) >= 2:
        header1 = headers[0]
        header2 = headers[1]

        print(f"Testing relationship between:")
        print(f"  H{header1.level}: {header1.title}")
        print(f"  H{header2.level}: {header2.title}")

        same_hierarchy = analyzer.are_under_same_hierarchy(
            header1.start_pos, header2.start_pos, max_level_difference=0
        )

        print(f"  Under same hierarchy (exact): {same_hierarchy}")

        same_hierarchy_lenient = analyzer.are_under_same_hierarchy(
            header1.start_pos, header2.start_pos, max_level_difference=1
        )

        print(f"  Under same hierarchy (±1 level): {same_hierarchy_lenient}")

    print()


def test_documentation_chunker():
    """Test the complete documentation chunking pipeline"""
    print_separator("Testing Documentation Chunker")

    # Test with different configurations
    configs = [
        {
            "name": "Standard Config",
            "max_tokens": 4000,
            "similarity_threshold": 0.80,
            "enable_merging": True
        },
        {
            "name": "Strict Config (no merging)",
            "max_tokens": 4000,
            "similarity_threshold": 0.80,
            "enable_merging": False
        },
        {
            "name": "Smaller Chunks",
            "max_tokens": 2000,
            "similarity_threshold": 0.80,
            "enable_merging": True
        }
    ]

    for config in configs:
        name = config.pop("name")
        print(f"\n--- {name} ---\n")

        chunker = DocumentationChunker(**config)
        chunks = chunker.chunk_document(
            SAMPLE_DOCUMENTATION,
            url="https://fastapi.tiangolo.com/",
            metadata={"source": "fastapi_docs"}
        )

        print(f"Chunks created: {len(chunks)}")

        # Statistics
        if chunks:
            token_counts = [c.token_count for c in chunks]
            print(f"Token counts:")
            print(f"  Min: {min(token_counts)}")
            print(f"  Max: {max(token_counts)}")
            print(f"  Average: {sum(token_counts) / len(token_counts):.0f}")
            print()

            # Show first 3 chunks
            print("First 3 chunks:")
            for i, chunk in enumerate(chunks[:3], 1):
                preview = chunk.content[:100].replace('\n', ' ')
                print(f"  Chunk {i}:")
                print(f"    Tokens: {chunk.token_count}")
                print(f"    Characters: {chunk.char_count}")
                print(f"    Preview: {preview}...")
                print(f"    Has code: {chunk.metadata.get('has_code', False)}")
                print(f"    Has table: {chunk.metadata.get('has_table', False)}")
                print(f"    Merged: {chunk.metadata.get('merged', False)}")
                print()

        print_separator()


def test_similarity():
    """Test similarity calculations"""
    print_separator("Testing Similarity Calculator")

    from webnexus.utils.similarity_calculator import SimilarityCalculator

    calculator = SimilarityCalculator()

    # Test similar texts
    text1 = "FastAPI is a modern web framework for building APIs with Python."
    text2 = "FastAPI is a web framework for creating APIs using Python."
    text3 = "React is a JavaScript library for building user interfaces."

    similarity_1_2 = calculator.compute_cosine_similarity(text1, text2)
    similarity_1_3 = calculator.compute_cosine_similarity(text1, text3)
    similarity_2_3 = calculator.compute_cosine_similarity(text2, text3)

    print("Similarity tests:")
    print(f"  Text 1 vs Text 2 (similar): {similarity_1_2:.2%}")
    print(f"  Text 1 vs Text 3 (different): {similarity_1_3:.2%}")
    print(f"  Text 2 vs Text 3 (different): {similarity_2_3:.2%}")
    print()

    # Test merge decision
    threshold = 0.80
    print(f"Merge threshold: {threshold:.0%}")
    print(f"  Would merge Text 1 & 2: {similarity_1_2 >= threshold}")
    print(f"  Would merge Text 1 & 3: {similarity_1_3 >= threshold}")

    print()


def main():
    """Run all tests"""
    print_separator("DOCUMENTATION CHUNKING STRATEGY TEST SUITE")

    try:
        # Run individual tests
        test_token_counter()
        test_markdown_parser()
        test_header_hierarchy()
        test_similarity()
        test_documentation_chunker()

        print_separator("✅ ALL TESTS COMPLETED SUCCESSFULLY")

    except Exception as e:
        print_separator("❌ TEST FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
