from __future__ import annotations

import os
from typing import List, Optional, Dict, Any
from uuid import uuid4
from hashlib import sha1
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv, find_dotenv

# optional imports guarded - these packages may not be installed in the environment
try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None

try:
    from langchain_pinecone import PineconeVectorStore
except Exception:
    PineconeVectorStore = None

try:
    from langchain_core.documents import Document
except Exception:
    Document = None

# Load env if present
load_dotenv(find_dotenv())

# LangChain helpers
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# prefer tiktoken for tokenization; fallback to simple splitter
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except Exception:
    tiktoken = None
    _TIKTOKEN_AVAILABLE = False

# local loaders (relative import within rag module)
from .loaders import CustomPDFLoader

# Try to reuse project-level helpers if available
try:
    from app import create_index
except Exception:
    create_index = None

import logging
logger = logging.getLogger(__name__)

# AWS client (for reading uploaded/class/{id_clase} files)
try:
    from ..aws.client import get_aws_client
    aws = get_aws_client()
except Exception:
    aws = None

import tempfile
import shutil

_PC = None  
_VECTOR_STORES = {} 

def init_pinecone(api_key: Optional[str] = None) -> Pinecone:
    """Inicializa y devuelve una instancia de Pinecone client (v6 style).

    Usa variables de entorno PINECONE_API_KEY y PINECONE_ENV si no se pasan.
    """
    global _PC
    api_key = api_key or os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY no está definida")
    _PC = Pinecone(api_key=api_key)
    return _PC

init_pinecone()

def get_index(index_name: str):
    """Devuelve el objeto Index para operaciones directas (pc.Index)
    Requiere init_pinecone haya sido llamado.
    """
    if _PC is None:
        raise RuntimeError("Pinecone client no inicializado. Llama a init_pinecone() primero.")
    return _PC.Index(index_name)


def create_namespace(index_name: str, namespace: str, seed_vector: Optional[List[float]] = None, metadata: Optional[dict] = None) -> str:
    """Crea un namespace dentro de un índice haciendo un upsert de un vector semilla.

    - seed_vector: lista opcional de floats; si no se provee se intentará inferir la
      dimensión del índice; si no puede inferirse se lanzará un error para que el
      caller provea seed_vector.
    - metadata: metadata opcional para el vector semilla.

    Devuelve el id del vector semilla insertado (útil para eliminarlo después si se desea).
    """
    if _PC is None:
        raise RuntimeError("Pinecone client no inicializado. Llama a init_pinecone() primero.")

    idx = get_index(index_name)

    # If no seed vector provided, try to infer index dimension
    if seed_vector is None:
        dim = None
        # Try various client methods to find dimension
        try:
            info = getattr(_PC, "describe_index", lambda name: None)(index_name)
            if info:
                dim = info.get("dimension") or info.get("index", {}).get("dimension")
        except Exception:
            dim = None

        try:
            info2 = getattr(idx, "describe_index", lambda: None)()
            if info2:
                dim = dim or info2.get("dimension")
        except Exception:
            pass

        if dim is None:
            raise RuntimeError("No se pudo inferir la dimensión del índice. Provee `seed_vector` para crear la namespace.")
        seed_vector = [0.0] * int(dim)

    vector_id = f"__ns_init__{uuid4().hex}"
    meta = metadata or {"_ns_init": True}
    try:
        idx.upsert(documents=[(vector_id, seed_vector, meta)], namespace=namespace)
    except TypeError:
        idx.upsert(documents=[(vector_id, seed_vector, meta)])

    return vector_id


def build_vector_store(index_name: str, embedding_model: Optional[str] = "text-embedding-3-small"):
    """Construye o devuelve un PineconeVectorStore asociado al índice.

    Requiere langchain_pinecone y langchain_openai instalados.
    """
    if PineconeVectorStore is None or OpenAIEmbeddings is None:
        raise RuntimeError("langchain_pinecone o langchain_openai no están instalados")
    if index_name in _VECTOR_STORES:
        return _VECTOR_STORES[index_name]

    index_obj = get_index(index_name)
    embeddings = OpenAIEmbeddings(model=embedding_model)
    vs = PineconeVectorStore(index=index_obj, embedding=embeddings)
    _VECTOR_STORES[index_name] = vs
    return vs


def add_documents_to_index(
    index_name: str,
    texts: List[str],
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
    namespace: Optional[str] = None,
) -> List[str]:
    """Añade únicamente textos al índice.

    - texts: lista de strings ya preprocesados/limpios.
    - metadatas: lista opcional de diccionarios paralelos a `texts`.
    - ids: lista opcional de ids; si no se proporcionan se generan UUIDs.

    La función intentará crear `langchain` Document objects y usar
    `PineconeVectorStore.add_documents`. Si `Document` no está disponible,
    calculará embeddings con `OpenAIEmbeddings` y hará `upsert` directo.
    Devuelve la lista de ids insertados.
    """
    if not texts:
        return []

    vs = build_vector_store(index_name)

    if metadatas is None:
        metadatas = [{} for _ in texts]

    if ids is None:
        ids = [str(uuid4()) for _ in texts]

    if Document is not None:
        docs = []
        for i, txt in enumerate(texts):
            meta = metadatas[i] if i < len(metadatas) else {}
            docs.append(Document(page_content=txt, metadata=meta))
        # try to pass namespace if the vector store supports it
        try:
            vs.add_documents(documents=docs, ids=ids, namespace=namespace)  # type: ignore
        except TypeError:
            vs.add_documents(documents=docs, ids=ids)
        return ids

    # Fallback: compute embeddings and upsert directly
    if OpenAIEmbeddings is None:
        raise RuntimeError("No hay forma de generar embeddings: instala langchain_openai o pasa Document objects")

    emb = OpenAIEmbeddings()
    # Use batch embedding if supported
    if hasattr(emb, "embed_documents"):
        vectors = emb.embed_documents(texts)
    else:
        vectors = [emb.embed_query(t) for t in texts]

    items = []
    for id_, vec, meta in zip(ids, vectors, metadatas):
        items.append((id_, vec, meta))

    index_obj = get_index(index_name)
    try:
        index_obj.upsert(documents=items, namespace=namespace)
    except TypeError:
        index_obj.upsert(documents=items)
    return ids


def delete_from_index(index_name: str, ids: List[str], namespace: Optional[str] = None):
    idx = get_index(index_name)
    try:
        idx.delete(ids=ids, namespace=namespace)
    except TypeError:
        idx.delete(ids=ids)


def list_indices() -> List[str]:
    if _PC is None:
        raise RuntimeError("Pinecone client no inicializado. Llama a init_pinecone() primero.")
    res = _PC.list_indexes()
    if isinstance(res, (list, tuple)):
        return [str(x) for x in res]

    names = None
    if hasattr(res, "names"):
        try:
            cand = res.names
            names = cand() if callable(cand) else cand
        except Exception:
            names = None

    if names is not None:
        try:
            return [str(x) for x in list(names)]
        except Exception:
            return [str(names)]

    try:
        return [str(x) for x in list(res)]
    except Exception:
        return [str(res)]


def similarity_query(index_name: str, query: str = None, vector: List[float] = None, k: int = 3, embedding_model: str = "text-embedding-3-small", namespace: Optional[str] = None):
    """Si se pasa `query` se calculará el embedding; si pasas `vector` se usa directamente.

    Devuelve los matches (incluyendo metadata) en forma de lista simple.
    """
    if query and vector:
        raise ValueError("Pasa solo 'query' o 'vector', no ambos")

    if query:
        if OpenAIEmbeddings is None:
            raise RuntimeError("OpenAIEmbeddings no disponible")
        emb = OpenAIEmbeddings(model=embedding_model)
        vector = emb.embed_query(query)

    idx = get_index(index_name)
    try:
        resp = idx.query(vector=vector, top_k=k, include_metadata=True, namespace=namespace)
    except TypeError:
        resp = idx.query(vector=vector, top_k=k, include_metadata=True)
    # Normalize results
    matches = []
    for m in getattr(resp, "matches", []) or resp.get("matches", []):
        matches.append({
            "id": m.id if hasattr(m, "id") else m.get("id"),
            "score": getattr(m, "score", m.get("score")),
            "metadata": getattr(m, "metadata", m.get("metadata")),
        })
    return matches

DEFAULT_INDEX = os.getenv("RAG_INDEX", "learningforlive")
# Read RAG_DIM env var, fall back to 1536 (matches most OpenAI embedding models like text-embedding-3-small)
DEFAULT_DIM = int(os.getenv("RAG_DIM", "1536"))


## --- Re-exported / wrapped app (Pinecone) helpers for RAG consumers ---


def rag_init_pinecone(api_key: str = None):
    """Inicializa el cliente Pinecone (delegado a app.init_pinecone)."""
    return init_pinecone(api_key=api_key)


def rag_create_namespace(index_name: str, namespace: str, seed_vector: list | None = None, metadata: dict | None = None):
    return create_namespace(index_name, namespace, seed_vector=seed_vector, metadata=metadata)


def rag_list_indices() -> list:
    return list_indices()


def rag_add_documents(index_name: str, texts: List[str], metadatas: Optional[List[dict]] = None, ids: Optional[List[str]] = None, namespace: Optional[str] = None) -> List[str]:
    return add_documents_to_index(index_name, texts, metadatas=metadatas, ids=ids, namespace=namespace)


def rag_similarity_query(index_name: str, query: str = None, vector: List[float] = None, k: int = 3, embedding_model: str = "text-embedding-3-small", namespace: Optional[str] = None):
    return similarity_query(index_name, query=query, vector=vector, k=k, embedding_model=embedding_model, namespace=namespace)


# simple_rag wrapper removed; use similarity_query + application logic instead


def _normalize_namespace(*parts: str) -> str:
    joined = "_".join([p.lower().strip().replace(" ", "_") for p in parts if p])
    for a, b in [("í", "i"), ("á", "a"), ("é", "e"), ("ó", "o"), ("ú", "u")]:
        joined = joined.replace(a, b)
    allowed = [c for c in joined if c.isalnum() or c in "_-"]
    ns = "".join(allowed)
    return ns or "default"


def _chunk_texts(texts: List[str], chunk_size: int = 1000, chunk_overlap: int = 0, tokens_per_chunk: int = 256) -> List[str]:
    if not texts:
        return []
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    joined = "\n\n".join(texts)
    char_chunks = splitter.split_text(joined)
    out: List[str] = []

    if _TIKTOKEN_AVAILABLE:
        enc_name = os.getenv("TIKTOKEN_ENCODING", "cl100k_base")
        enc = None
        try:
            enc = tiktoken.get_encoding(enc_name)
        except Exception:
            try:
                enc = tiktoken.encoding_for_model(os.getenv("TIKTOKEN_MODEL", "text-embedding-3-small"))
            except Exception:
                enc = None

        for c in char_chunks:
            if not c or not c.strip():
                continue
            if enc is None:
                toks = c.split()
                # fallback to whitespace chunking
                step = max(tokens_per_chunk - chunk_overlap, 1)
                for i in range(0, len(toks), step):
                    out.append(" ".join(toks[i : i + tokens_per_chunk]))
                continue

            toks = enc.encode(c)
            if not toks:
                continue
            step = max(tokens_per_chunk - chunk_overlap, 1)
            for i in range(0, len(toks), step):
                chunk_tokens = toks[i : i + tokens_per_chunk]
                try:
                    decoded = enc.decode(chunk_tokens)
                except Exception:
                    decoded = " ".join(map(str, chunk_tokens))
                out.append(decoded)

        return out

    # fallback: whitespace-based token chunking with overlap
    def _simple_token_split(text: str, tokens_per_chunk: int, overlap: int) -> List[str]:
        tokens = text.split()
        if not tokens:
            return []
        if len(tokens) <= tokens_per_chunk:
            return [text]
        out_chunks: List[str] = []
        step = max(tokens_per_chunk - overlap, 1)
        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i : i + tokens_per_chunk]
            out_chunks.append(" ".join(chunk_tokens))
        return out_chunks

    for c in char_chunks:
        out.extend(_simple_token_split(c, tokens_per_chunk, chunk_overlap))
    return out


def _deterministic_id(text: str) -> str:
    return sha1(text.encode("utf-8")).hexdigest()


def extract_pdf_texts(pdf_path: str) -> List[str]:
    if not os.path.exists(pdf_path):
        logger.warning("PDF not found: %s", pdf_path)
        return []
    loader = CustomPDFLoader(pdf_path)
    docs = loader.load()
    texts: List[str] = []
    for d in docs:
        c = getattr(d, "page_content", "")
        if c and c.strip():
            texts.append(c.strip())
    return texts


def ensure_index_and_namespace(index_name: str = DEFAULT_INDEX, namespace: Optional[str] = None, dimension: int = DEFAULT_DIM):
    """Ensure the index exists and optionally create the namespace (seed).

    This will attempt to create the index with `dimension` if the project-level
    helper `create_index` is available. After creation (or if the index already
    exists) we check the actual index dimension and raise a clear error if it
    doesn't match the requested `dimension`. This avoids a confusing Pinecone
    400 error when upserting vectors with a mismatched size.
    """

    # Try to create the index with the requested dimension if helper exists
    if create_index is None:
        logger.debug("create_index helper not available; assuming index was created externally")
    else:
        try:
            create_index(index_name, dimension=dimension)
        except Exception as e:
            # creation may fail if index exists with different params; log and continue
            logger.debug("create_index warning: %s", e)

    # Inspect actual index dimension (best-effort) and validate
    def _get_index_dimension() -> Optional[int]:
        try:
            # prefer top-level client describe
            if _PC is not None and hasattr(_PC, "describe_index"):
                info = _PC.describe_index(index_name)
                if info:
                    dim = info.get("dimension") or (info.get("index") or {}).get("dimension")
                    if dim:
                        return int(dim)
        except Exception:
            pass
        try:
            idx = get_index(index_name)
            if hasattr(idx, "describe_index"):
                info2 = idx.describe_index()
                if info2:
                    dim2 = info2.get("dimension")
                    if dim2:
                        return int(dim2)
        except Exception:
            pass
        return None

    actual_dim = _get_index_dimension()
    if actual_dim is not None and actual_dim != int(dimension):
        raise RuntimeError(
            f"Index '{index_name}' dimension mismatch: index has dimension {actual_dim} but expected {int(dimension)}. "
            "Either set RAG_DIM to the embedding size (e.g. 1536) or recreate the index with the correct dimension/embedding model."
        )

    # Namespace creation (seed vector) - best-effort
    if namespace:
        if create_namespace is None:
            logger.debug("create_namespace helper not available; namespace will be created on upsert if supported by the client")
        else:
            try:
                create_namespace(index_name, namespace)
            except Exception as e:
                # Not fatal; namespace will be created on first upsert if client doesn't support explicit creation
                logger.debug("create_namespace warning: %s", e)


def process_pdf_collection(
    pdf_path: str,
    docente: str,
    id_clase: str,
    index_name: str = DEFAULT_INDEX,
    chunk_size: int = 1000,
    chunk_overlap: int = 0,
    tokens_per_chunk: int = 256,
    dedupe: bool = True,
    dimension: int = DEFAULT_DIM,
) -> Dict[str, Any]:
    collection_name = f"data_{docente.lower().replace(' ', '_')}_{id_clase}"
    namespace = _normalize_namespace(collection_name)

    ensure_index_and_namespace(index_name, namespace, dimension=dimension)

    # If pdf_path points to an S3 location (uploaded/class/{id_clase}/...), download it first
    local_pdf = None
    try:
        if aws and aws.is_enabled() and pdf_path and (pdf_path.startswith("uploaded/") or pdf_path.startswith("/uploaded/") or pdf_path.startswith("s3://")):
            client = aws.get_client()
            bucket = aws.get_bucket()
            if client is None or bucket is None:
                raise RuntimeError("S3 client or bucket not configured")
            # normalize key
            key = pdf_path[1:] if pdf_path.startswith("/") else pdf_path
            # remove s3://bucket/ prefix if present
            if key.startswith("s3://"):
                # s3://bucket/key
                parts = key.split("/", 3)
                if len(parts) >= 4:
                    key = parts[3]
                elif len(parts) == 3:
                    key = parts[2]

            tmpdir = tempfile.mkdtemp(prefix="rag_pdf_")
            local_pdf = os.path.join(tmpdir, os.path.basename(key))
            client.download_file(bucket, key, local_pdf)
            texts = extract_pdf_texts(local_pdf)
        else:
            texts = extract_pdf_texts(pdf_path)
    finally:
        if local_pdf:
            try:
                shutil.rmtree(os.path.dirname(local_pdf), ignore_errors=True)
            except Exception:
                pass
    if not texts:
        return {"ok": False, "reason": "no_text_extracted"}

    chunks = _chunk_texts(texts, chunk_size=chunk_size, chunk_overlap=chunk_overlap, tokens_per_chunk=tokens_per_chunk)
    if not chunks:
        return {"ok": False, "reason": "no_chunks"}

    # prepare metadatas and ids
    metadatas = [{"source": os.path.basename(pdf_path), "collection": collection_name, "chunk_index": i, "text": chunk[:2000]} for i, chunk in enumerate(chunks)]
    if dedupe:
        ids = [_deterministic_id(ch) for ch in chunks]
    else:
        ids = [str(uuid4()) for _ in chunks]

    # upsert via add_documents_to_index (expects cleaned texts)
    upserted_ids = add_documents_to_index(index_name, chunks, metadatas=metadatas, ids=ids, namespace=namespace)

    return {"ok": True, "index": index_name, "namespace": namespace, "upserted": len(upserted_ids), "ids": upserted_ids}


def process_class_files(
    id_clase: str,
    folder_path: Optional[str] = None,
    index_name: str = DEFAULT_INDEX,
    chunk_size: int = 1000,
    chunk_overlap: int = 0,
    tokens_per_chunk: int = 256,
    dedupe: bool = True,
    dimension: int = DEFAULT_DIM,
    **kwargs,
) -> Dict[str, Any]:
    all_texts: List[str] = []
    sources: List[str] = []

    if aws and aws.is_enabled():
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is not None and bucket is not None:
            prefix = f"uploaded/class/{id_clase}/"
            try:
                paginator = client.get_paginator('list_objects_v2')
                pdf_keys = []
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get('Contents', []):
                        key = obj.get('Key')
                        if key and key.lower().endswith('.pdf'):
                            pdf_keys.append(key)

                if pdf_keys:
                    s3_processed = True
                    tmpdir = tempfile.mkdtemp(prefix=f"rag_class_{id_clase}_")
                    try:
                        for key in pdf_keys:
                            local_path = os.path.join(tmpdir, os.path.basename(key))
                            client.download_file(bucket, key, local_path)
                            extracted = extract_pdf_texts(local_path)
                            if extracted:
                                all_texts.extend(extracted)
                                sources.extend([os.path.basename(key)] * len(extracted))
                    finally:
                        try:
                            shutil.rmtree(tmpdir, ignore_errors=True)
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("S3 class files listing/download failed: %s", e)


    if not all_texts:
        return {"ok": False, "reason": "no_texts_extracted"}

    chunks = _chunk_texts(all_texts, chunk_size=chunk_size, chunk_overlap=chunk_overlap, tokens_per_chunk=tokens_per_chunk)
    if not chunks:
        return {"ok": False, "reason": "no_chunks"}

    metadatas = [{"source": sources[i] if i < len(sources) else "", "chunk_index": i, "class_id": id_clase, "text": chunk[:2000]} for i, chunk in enumerate(chunks)]
    if dedupe:
        ids = [_deterministic_id(ch) for ch in chunks]
    else:
        ids = [str(uuid4()) for _ in chunks]

    collection_name = f"clase_{id_clase}"
    namespace = _normalize_namespace(collection_name)

    ensure_index_and_namespace(index_name, namespace, dimension=dimension)

    upserted_ids = add_documents_to_index(index_name, chunks, metadatas=metadatas, ids=ids, namespace=namespace)
    return {"ok": True, "index": index_name, "namespace": namespace, "upserted": len(upserted_ids)}


def retrieve_top_k_documents(query: str, index_name: str = DEFAULT_INDEX, top_k: int = 5, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve the top_k matching documents for a query from Pinecone.

    Returns a list of dicts with keys: id, score, metadata, text
    """
    matches = similarity_query(index_name, query=query, k=top_k, namespace=namespace)
    out: List[Dict[str, Any]] = []
    for m in matches:
        meta = m.get("metadata") or {}
        # try to extract text from metadata first
        text = None
        if isinstance(meta, dict):
            text = meta.get("text") or meta.get("content") or meta.get("page_content")
        # fallback to top-level fields
        if not text:
            text = m.get("text") or m.get("document") or None

        # debug: print short preview of retrieved item
        try:
            preview = (text or "")[:300]
            print(f"RAG retrieve: id={m.get('id')} score={m.get('score')} preview={preview}")
        except Exception:
            pass

        out.append({
            "id": m.get("id"),
            "score": m.get("score"),
            "metadata": meta,
            "text": text,
        })
    return out


__all__ = [
    "process_pdf_collection",
    "process_class_files",
    "ensure_index_and_namespace",
    "retrieve_top_k_documents",
]
