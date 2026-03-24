"""
Document Indexer — chunks minzdrav_dataset/ and builds ChromaDB vector index.

Chunking strategy:
1. Strip preamble (repeated TOC from HTML scraping)
2. Split by H1 headers (# Section)
3. Sub-chunk large sections by paragraphs (target 1000-2000 chars)
4. Embed with OpenAI text-embedding-3-small
5. Store in ChromaDB with persistent directory
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger()


def _extract_title(text: str) -> str:
    """Extract document title from the preamble."""
    match = re.search(r'Клинические рекомендации(.+?)(?:\n|Кодирование)', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _strip_preamble(text: str) -> str:
    """Remove repeated TOC/navigation blocks from scraped HTML."""
    markers = [
        "# Список сокращений",
        "# Термины и определения",
        "# 1. Краткая информация",
        "# 1.",
    ]
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            return text[idx:]
    return text


def chunk_document(filepath: str) -> List[Dict]:
    """
    Chunk a single minzdrav markdown file into sections with metadata.

    Returns list of dicts: {"text": ..., "metadata": {"source_file": ..., "section": ..., "document_title": ...}}
    """
    text = Path(filepath).read_text(encoding="utf-8")
    filename = os.path.basename(filepath)
    title = _extract_title(text)
    content = _strip_preamble(text)

    # Split on H1 headers
    sections = re.split(r'\n(?=# )', content)

    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(r'# (.+)', section)
        section_name = header_match.group(1).strip() if header_match else "unknown"
        body = section[header_match.end():].strip() if header_match else section.strip()

        if len(body) < 50:
            continue

        metadata = {
            "source_file": filename,
            "section": section_name,
            "document_title": title,
        }

        if len(body) <= 2000:
            chunks.append({"text": body, "metadata": metadata})
        else:
            # Sub-chunk by paragraphs
            paragraphs = body.split("\n\n")
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > 1500 and current_chunk:
                    chunks.append({"text": current_chunk.strip(), "metadata": metadata.copy()})
                    current_chunk = para
                else:
                    current_chunk = current_chunk + "\n\n" + para if current_chunk else para
            if current_chunk.strip() and len(current_chunk.strip()) >= 50:
                chunks.append({"text": current_chunk.strip(), "metadata": metadata.copy()})

    return chunks


class DocumentIndexer:
    """Indexes minzdrav documents into ChromaDB for evidence search."""

    COLLECTION_NAME = "minzdrav_grounding"

    def __init__(self, dataset_path: str, persist_directory: str, embedding_model: str = "text-embedding-3-small"):
        self.dataset_path = Path(dataset_path)
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None

    async def initialize(self):
        """Load or build the ChromaDB index."""
        import chromadb

        self._client = chromadb.PersistentClient(path=self.persist_directory)

        # Check if collection already exists and has data
        try:
            self._collection = self._client.get_collection(
                name=self.COLLECTION_NAME,
            )
            count = self._collection.count()
            if count > 0:
                logger.info("Loaded existing ChromaDB index", collection=self.COLLECTION_NAME, chunks=count)
                return
        except Exception:
            pass

        # Build index from scratch
        logger.info("Building ChromaDB index from documents", dataset_path=str(self.dataset_path))
        await self._build_index()

    async def _build_index(self):
        """Process all documents and build the ChromaDB index."""
        import chromadb

        # Create or get collection (without embedding function — we'll add embeddings manually)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Collect all chunks
        all_chunks = []
        md_files = sorted(self.dataset_path.glob("*.md"))

        if not md_files:
            logger.warning("No markdown files found in dataset path", path=str(self.dataset_path))
            return

        for filepath in md_files:
            try:
                chunks = chunk_document(str(filepath))
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning("Failed to chunk document", file=str(filepath), error=str(e))

        if not all_chunks:
            logger.warning("No chunks extracted from documents")
            return

        logger.info("Chunks extracted", total_chunks=len(all_chunks), total_files=len(md_files))

        # Embed all chunks via OpenAI
        from langchain_openai import OpenAIEmbeddings
        from app.config import settings

        api_key = settings.llm_api_key or settings.openai_api_key
        embeddings = OpenAIEmbeddings(model=self.embedding_model, api_key=api_key)

        # Batch embed
        texts = [c["text"] for c in all_chunks]
        BATCH_SIZE = 100
        all_embeddings = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            batch_embeddings = await embeddings.aembed_documents(batch)
            all_embeddings.extend(batch_embeddings)
            logger.info("Embedded batch", batch=f"{i+1}-{min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

        # Add to ChromaDB in batches
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch_end = min(i + BATCH_SIZE, len(all_chunks))
            self._collection.add(
                ids=[f"chunk_{j}" for j in range(i, batch_end)],
                documents=[all_chunks[j]["text"] for j in range(i, batch_end)],
                embeddings=[all_embeddings[j] for j in range(i, batch_end)],
                metadatas=[all_chunks[j]["metadata"] for j in range(i, batch_end)],
            )

        logger.info("ChromaDB index built", total_chunks=len(all_chunks))

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search the index for chunks relevant to the query.

        Returns list of dicts with keys: text, metadata, relevance_score.
        """
        if not self._collection or self._collection.count() == 0:
            return []

        from langchain_openai import OpenAIEmbeddings
        from app.config import settings

        api_key = settings.llm_api_key or settings.openai_api_key
        embeddings = OpenAIEmbeddings(model=self.embedding_model, api_key=api_key)

        query_embedding = await embeddings.aembed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results and results["documents"] and results["documents"][0]:
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                # Convert to similarity: 1 - distance/2
                similarity = 1.0 - distance / 2.0
                search_results.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance_score": similarity,
                })

        return search_results
