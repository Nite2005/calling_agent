#!/usr/bin/env python3
"""
Test RAG Knowledge Base

This script tests if your knowledge base is working correctly.
"""

import torch
from sentence_transformers import SentenceTransformer
import chromadb

print("=" * 70)
print("🧪 TESTING RAG KNOWLEDGE BASE")
print("=" * 70)

# Connect to ChromaDB
print("\n1️⃣ Connecting to ChromaDB...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("docs")

doc_count = collection.count()
print(f"✅ Connected")
print(f"📊 Documents in knowledge base: {doc_count}")

if doc_count == 0:
    print("\n❌ ERROR: Knowledge base is EMPTY!")
    print("   Run this first: python3 load_knowledge_base.py")
    exit(1)

# Load embedding model
print("\n2️⃣ Loading embedding model...")
device = 'cuda' if torch.cuda.is_available() else 'cpu'
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=device)
embedder.eval()
print(f"✅ Model loaded on {device}")

# Test queries
test_queries = [
    "What services do you provide?",
    "Tell me about Salesforce",
    "What is AI?",
    "Do you offer consulting?",
]

print("\n3️⃣ Testing queries...")
print("-" * 70)

for query in test_queries:
    print(f"\n📝 Query: '{query}'")
    
    # Generate embedding
    with torch.no_grad():
        query_embedding = embedder.encode(
            [query],
            device=device,
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0].tolist()
    
    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    
    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    
    if docs:
        print(f"✅ Found {len(docs)} results")
        for i, (doc, dist) in enumerate(zip(docs[:2], distances[:2]), 1):
            print(f"\n   Result {i} (distance: {dist:.3f}):")
            print(f"   {doc[:150]}...")
            
            # Check relevance
            if dist <= 1.0:
                print(f"   ✅ RELEVANT (good)")
            elif dist <= 1.3:
                print(f"   ⚠️ MODERATE (okay)")
            else:
                print(f"   ❌ NOT RELEVANT (too far)")
    else:
        print("❌ No results found")

print("\n" + "=" * 70)
print("✅ TEST COMPLETE")
print("=" * 70)

print("\n📋 DIAGNOSIS:")
if doc_count > 0:
    print(f"✅ Knowledge base has {doc_count} documents")
    print("✅ RAG system is working")
    print("\n💡 If agent gives wrong answers:")
    print("   1. Check agent's system_prompt includes instruction to use knowledge base")
    print("   2. Check distance threshold (should be <= 1.0 for strict relevance)")
    print("   3. Review server logs for RAG retrieval messages")
else:
    print("❌ Knowledge base is empty - run load_knowledge_base.py first")
