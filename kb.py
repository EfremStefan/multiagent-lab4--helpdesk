"""Part B - knowledge base: chunking, embeddings, cached cosine retrieval."""
import argparse
import hashlib
import json
import re

import numpy as np
import ollama

import config


def chunk_markdown(text, max_chars=900, overlap=150):
    sections = re.split(r"\n(?=#{1,3} )", text)  # split before headings
    chunks = []
    for sec in sections:
        if not sec.strip():
            continue
        title = sec.strip().splitlines()[0].lstrip("# ").strip()
        body = sec.strip()
        start = 0
        while start < len(body):
            piece = body[start:start + max_chars]
            chunks.append({"id": len(chunks), "section": title, "text": piece})
            if start + max_chars >= len(body):
                break
            start += max_chars - overlap
    return chunks


class KnowledgeBase:
    def __init__(self, path=config.MANUAL_PATH, chunk_size=None):
        self.path = path
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        text = open(path, encoding="utf-8").read()
        self.text = text
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.chunks, self.matrix = self._load_or_build(text)

    def _cache_paths(self):
        config.CACHE_DIR.mkdir(exist_ok=True)
        stem = config.CACHE_DIR / f"kb_{self.chunk_size}"
        return stem.with_suffix(".npy"), stem.with_suffix(".json")

    def _load_or_build(self, text):
        npy, meta = self._cache_paths()
        if npy.exists() and meta.exists():
            info = json.loads(meta.read_text(encoding="utf-8"))
            if info.get("sha256") == self.sha256 and info.get("embed_model") == config.EMBED_MODEL:
                return info["chunks"], np.load(npy)

        chunks = chunk_markdown(text, max_chars=self.chunk_size, overlap=config.CHUNK_OVERLAP)
        docs = ["search_document: " + c["section"] + "\n" + c["text"] for c in chunks]
        vecs = np.array(ollama.embed(model=config.EMBED_MODEL, input=docs)["embeddings"])
        matrix = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        np.save(npy, matrix)
        meta.write_text(json.dumps({
            "sha256": self.sha256,
            "embed_model": config.EMBED_MODEL,
            "chunk_size": self.chunk_size,
            "chunks": chunks,
        }, ensure_ascii=False), encoding="utf-8")
        return chunks, matrix

    def search(self, query, k=4):
        q = np.array(ollama.embed(model=config.EMBED_MODEL,
                                  input="search_query: " + query)["embeddings"][0])
        q = q / np.linalg.norm(q)
        scores = self.matrix @ q
        best = np.argsort(-scores)[:k]
        return [dict(self.chunks[i], score=float(scores[i])) for i in best]


def demo():
    kb = KnowledgeBase()
    print(f"{len(kb.chunks)} chunks (chunk size {kb.chunk_size}), manual sha256 {kb.sha256[:12]}...")
    for query in ["E07", "lion's mane humidity", "bleach"]:
        print(f"\nQuery: {query}")
        for hit in kb.search(query, k=3):
            print(f"  {hit['score']:.3f}  [{hit['section']}]  chunk {hit['id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Task B1: top-3 chunks for three queries")
    args = parser.parse_args()
    if args.demo:
        demo()
    else:
        parser.print_help()
