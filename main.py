from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.mongo import db
from app.middleware.logging import LoggingMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS
origins = [
    "https://staging.d3tjq91xrdvf87.amplifyapp.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

@app.on_event("startup")
async def startup_db_client():
    db.connect()
    # Ensure MongoDB indexes exist (idempotent — safe to run on every boot)
    from app.repositories.entries import EntriesRepository
    await EntriesRepository().ensure_indexes()


@app.on_event("shutdown")
async def shutdown_db_client():
    db.close()

@app.get("/")
def root():
    return {"message": "Welcome to OneTwenty SaaS API"}

app.include_router(api_router, prefix=settings.API_V1_STR)
