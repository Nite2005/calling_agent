#!/usr/bin/env python3
"""
Load Knowledge Base Data into ChromaDB

This script loads your data file into the RAG vector database.
Run this ONCE before starting your server.
"""

import os
import torch
from sentence_transformers import SentenceTransformer
import chromadb
from tqdm import tqdm

# Configuration
DATA_FILE = "./data/data.txt"
CHROMA_PATH = "./chroma_db"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 384
BATCH_SIZE = 32

print("=" * 70)
print("📚 LOADING KNOWLEDGE BASE INTO RAG SYSTEM")
print("=" * 70)

# Check if data file exists
if not os.path.exists(DATA_FILE):
    print(f"\n❌ ERROR: Data file not found at {DATA_FILE}")
    print("Please ensure your data file exists at this location.")
    exit(1)

# Detect GPU
if torch.cuda.is_available():
    device = 'cuda'
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
elif torch.backends.mps.is_available():
    device = 'mps'
    print("✅ Apple Silicon GPU detected")
else:
    device = 'cpu'
    print("⚠️ Using CPU (slower)")

# Load embedding model
print(f"\n📦 Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL, device=device)
embedder.eval()

if device == 'cuda':
    try:
        embedder.half()
        print("✅ FP16 enabled")
    except:
        pass

# Connect to ChromaDB
print(f"\n🔗 Connecting to ChromaDB: {CHROMA_PATH}")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection("docs")

# Check existing data
existing_count = collection.count()
print(f"📊 Current documents: {existing_count}")

if existing_count > 0:
    response = input(f"\n⚠️ Found {existing_count} existing documents. Delete and reload? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        print("🗑️ Deleting collection...")
        chroma_client.delete_collection("docs")
        collection = chroma_client.get_or_create_collection("docs")
        print("✅ Cleared")
    else:
        print("❌ Cancelled")
        exit(0)

# Read data file
print(f"\n📖 Reading: {DATA_FILE}")
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

print(f"✅ Loaded {len(text):,} characters")

# Chunk the text
def chunk_text(text, chunk_size=384, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks

print(f"\n✂️ Chunking text...")
chunks = chunk_text(text, CHUNK_SIZE)
print(f"✅ Created {len(chunks):,} chunks")

# Generate embeddings and add to ChromaDB
print(f"\n🔥 Generating embeddings...")
import time
start = time.time()

for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Processing"):
    batch = chunks[i:i + BATCH_SIZE]
    ids = [f"doc_{i+j}" for j in range(len(batch))]
    
    with torch.no_grad():
        embeddings = embedder.encode(
            batch,
            device=device,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=BATCH_SIZE
        )
    
    collection.add(
        ids=ids,
        documents=batch,
        embeddings=embeddings.tolist()
    )

elapsed = time.time() - start
print(f"\n✅ COMPLETE!")
print(f"   Documents: {collection.count():,}")
print(f"   Time: {elapsed:.1f}s")
print(f"   Speed: {len(chunks)/elapsed:.1f} docs/sec")

# Test query
print(f"\n🧪 Testing...")
test = "What services do you provide?"
with torch.no_grad():
    q_emb = embedder.encode([test], device=device, convert_to_numpy=True, normalize_embeddings=True)[0].tolist()

results = collection.query(query_embeddings=[q_emb], n_results=3)
print(f"✅ Query test successful - found {len(results['documents'][0])} results")

print("\n" + "=" * 70)
print("✅ KNOWLEDGE BASE IS READY!")
print("=" * 70)
print("\nYou can now start your server:")
print("  uvicorn main:app --host 0.0.0.0 --port 9001")
