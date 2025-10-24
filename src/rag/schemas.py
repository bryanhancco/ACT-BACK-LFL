from pydantic import BaseModel
from typing import Optional, List


class ProcessPDFRequest(BaseModel):
    pdf_path: str
    docente: str
    id_clase: str
    index_name: Optional[str] = None
    chunk_size: int = 1000
    chunk_overlap: int = 0
    tokens_per_chunk: int = 256
    dedupe: bool = True


class ProcessClassRequest(BaseModel):
    id_clase: str
    folder_path: str
    docente: Optional[str] = "class"
    index_name: Optional[str] = None
    chunk_size: int = 1000
    chunk_overlap: int = 0
    tokens_per_chunk: int = 256
    dedupe: bool = True


class EnsureIndexRequest(BaseModel):
    index_name: str
    namespace: Optional[str] = None


class RetrieveRequest(BaseModel):
    query: str
    index_name: Optional[str] = None
    top_k: int = 5
    namespace: Optional[str] = None


class RetrieveDoc(BaseModel):
    id: Optional[str]
    score: Optional[float]
    metadata: Optional[dict]
    text: Optional[str]


class RetrieveResponse(BaseModel):
    docs: List[RetrieveDoc]
