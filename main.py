from http.client import HTTPException
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware



# Ensure project root is on sys.path so `import src.*` works reliably in all
# environments (local, Render, Docker, etc.). Some platforms change the
# working directory when launching the process which can make 'src' not
# importable unless the project root is present in sys.path.
import os
import sys

from src.estudiante.schema import EstudianteLoginDTO, EstudianteResponseDTO
from src.estudiante import service

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    # Insert at front so local packages take precedence over site-packages
    sys.path.insert(0, PROJECT_ROOT)

app = FastAPI(title="LearningForLive", description="API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  
        "http://lfl-nlb-5909a369bb7b3f29.elb.us-east-2.elb.amazonaws.com",
    ],
    # Accept dynamic ngrok subdomains and ELB hostnames via regex.
    # Match origins that end with ngrok-free.app, ngrok.io or elb.amazonaws.com
    # and allow multiple subdomain labels (e.g. lfl-frontend-elb-... .us-east-2.elb.amazonaws.com).
    allow_origin_regex=r"^https?://([A-Za-z0-9-]+\.)*elb\.amazonaws\.com$|^https?://([A-Za-z0-9-]+\.)*(ngrok-free\.app|ngrok\.io)$",
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

# Rely on Starlette/FastAPI CORSMiddleware to manage CORS preflights and headers.
# The previous custom `cors_handler` middleware was removed because it could
# interfere with CORSMiddleware ordering and cause missing Access-Control headers
# on OPTIONS requests.


# Lightweight logging middleware for debugging Origin headers (non-invasive).
# This middleware only logs the Origin header and forwards the request. It does
# not modify responses or short-circuit OPTIONS preflights, so CORSMiddleware
# remains responsible for CORS headers.
@app.middleware("http")
async def log_origin_header(request, call_next):
    try:
        origin = request.headers.get("origin")
        if origin:
            # Use print so messages appear in container stdout (ECS task logs)
            print(f"[CORS DEBUG] Received Origin: {origin}")
    except Exception:
        pass
    response = await call_next(request)
    return response


@app.get("/")
async def read_root():
    return {"message": "Hola mundo"}

@app.post("/login")
async def login_estudiante(login_data: EstudianteLoginDTO):
    try:
        user = service.find_by_email(login_data.correo)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        if not service.verify_password(login_data.password, user['password']):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        user.pop('password', None)
        return {"message": "Login exitoso", "estudiante": EstudianteResponseDTO(**user)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
