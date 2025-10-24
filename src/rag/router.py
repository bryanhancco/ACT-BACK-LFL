from fastapi import APIRouter, Body, HTTPException
from typing import Optional

from . import service as rag_service
from . import schemas

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ensure-index")
def ensure_index(req: schemas.EnsureIndexRequest = Body(...)):
    try:
        idx = rag_service.ensure_index(req.index_name)
        if req.namespace:
            rag_service.ensure_namespace(req.index_name, req.namespace)
        return {"ok": True, "index": req.index_name, "namespace": req.namespace}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-pdf")
def process_pdf(req: schemas.ProcessPDFRequest = Body(...)):
    try:
        res = rag_service.process_pdf_collection(req.pdf_path, req.docente, req.id_clase, index_name=req.index_name, chunk_size=req.chunk_size, chunk_overlap=req.chunk_overlap, tokens_per_chunk=req.tokens_per_chunk, dedupe=req.dedupe)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-class")
def process_class(req: dict = Body(...)):
    try:
        id_clase = req.get("id_clase")
        if not id_clase:
            raise HTTPException(status_code=400, detail="'id_clase' is required in the request body")

        folder_path = req.get("folder_path")

        res = rag_service.process_class_files(id_clase, folder_path=folder_path)
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/namespace")
def delete_namespace(index_name: str, namespace: str):
    try:
        res = rag_service.delete_namespace(index_name, namespace)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve")
def retrieve(req: schemas.RetrieveRequest = Body(...)):
    try:
        docs = rag_service.retrieve_top_k_documents(req.query, index_name=req.index_name, top_k=req.top_k, namespace=req.namespace)
        return {"docs": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
