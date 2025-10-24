from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on sys.path so `import src.*` works reliably in all
# environments (local, Render, Docker, etc.). Some platforms change the
# working directory when launching the process which can make 'src' not
# importable unless the project root is present in sys.path.
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    # Insert at front so local packages take precedence over site-packages
    sys.path.insert(0, PROJECT_ROOT)

app = FastAPI(title="LearningForLive", description="API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  
        "http://127.0.0.1:3000",
        "http://localhost:3001", 
        "https://ia-docente-frontend.vercel.app",  
        "https://*.vercel.app",
        # note: wildcard patterns like "https://*.ngrok-free.app" are not matched by
        # CORSMiddleware's exact-origin matching. We'll use allow_origin_regex below
        # to permit dynamic ngrok subdomains.
        "https://your-production-domain.com", 
    ],
    # Accept dynamic ngrok subdomains (ngrok-free.app and ngrok.io) via regex
    allow_origin_regex=r"^https:\/\/([a-z0-9-]+\.)?(ngrok-free\.app|ngrok\.io)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "ngrok-skip-browser-warning", 
        "X-Forwarded-For",
        "X-Forwarded-Proto",
        "X-Real-IP",
    ],
)

@app.middleware("http")
async def cors_handler(request, call_next):
    origin = request.headers.get("origin")
    # If this is a preflight request, return CORS headers immediately
    allowed_origins = [
        "https://ia-docente-frontend.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    def apply_cors_headers(resp: Response):
        if origin:
            if (origin in allowed_origins or
                "ngrok-free.app" in origin or
                "ngrok.io" in origin or
                "vercel.app" in origin or
                "localhost" in origin):
                resp.headers["Access-Control-Allow-Origin"] = origin

        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH"
        resp.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers, ngrok-skip-browser-warning, X-Forwarded-For, X-Forwarded-Proto, X-Real-IP"

        if origin and "ngrok" in str(origin):
            resp.headers["ngrok-skip-browser-warning"] = "true"

    if request.method == "OPTIONS":
        # reply to preflight
        preflight_resp = Response(status_code=200)
        apply_cors_headers(preflight_resp)
        return preflight_resp

    try:
        response = await call_next(request)
    except Exception as e:
        # Ensure even on internal errors we return CORS headers so browser can see the response
        error_body = {"detail": str(e)}
        response = JSONResponse(content=error_body, status_code=500)

    apply_cors_headers(response)
    return response

@app.get("/")
async def read_root():
    return {"message": "Hola mundo"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

# Include routers if available (safe imports)
try:
    from src.files.router import router as files_router
    app.include_router(files_router)
except Exception as e:
    print(f"files router not included: {e}")
    
try:
    from src.docente.router import router as docente_router
    app.include_router(docente_router)
except Exception as e:
    print(f"docente router not included: {e}")
    
try:
    from src.clase.router import router as clase_router
    app.include_router(clase_router)
except Exception as e:
    print(f"clase router not included: {e}")

try:
    from src.rag.router import router as rag_router
    app.include_router(rag_router)
except Exception as e:
    print(f"rag router not included: {e}")

try:
    from src.generative_ai.router import router as gen_router
    app.include_router(gen_router)
except Exception as e:
    try:
        from src.generative_ai import router as gen_router_module
        app.include_router(gen_router_module.router)
    except Exception:
        print(f"gen module router not included: {e}")

try:
    from src.estudiante.router import router as estudiante_router
    app.include_router(estudiante_router)
except Exception as e:
    print(f"estudiante router not included: {e}")

try:
    from src.estudiante_clase.router import router as estudiante_clase_router
    app.include_router(estudiante_clase_router)
except Exception as e:
    print(f"estudiante_clase router not included: {e}")

try:
    from src.estudiante_contenido.router import router as estudiante_contenido_router
    app.include_router(estudiante_contenido_router)
except Exception as e:
    print(f"estudiante_contenido router not included: {e}")

try:
    from src.nota.router import router as nota_router
    app.include_router(nota_router)
except Exception as e:
    print(f"nota router not included: {e}")

try:
    from src.conversacion.router import router as conversacion_router
    app.include_router(conversacion_router)
except Exception as e:
    print(f"conversacion router not included: {e}")
