bind = "0.0.0.0:8000"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
# Increase timeout to accommodate long-running background tasks invoked by
# endpoints that may call external services (RAG / generative AI). For a
# production-grade fix, consider using a job queue (Celery/RQ) and keep web
# workers short-lived.
timeout = 600