import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database.postgres_session import engine
from app.database.postgres_models import (
    Base,
    User,
    Flight,
    RetailerUser,
    RetailerOffer,
    Reminder,
)
from app.core.config import FRONTEND_URL

from app.api import auth_routes, flights_routes, chat_routes, admin_routes

try:
    from app.jobs.scheduler_setup import start_scheduler, shutdown_scheduler
    HAS_SCHEDULER  = True
except:
    HAS_SCHEDULER = False

logging.basicConfig(level = logging.INFO, format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",)
logger = logging.getLogger("airport_companion_api")

logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application initialization on startup and graceful cleanup on shutdown.
    """

    logger.info("Starting up Airport Companion API...")

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL database tables verified/created successfully.")

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}", exc_info=True)

    if HAS_SCHEDULER:
        try:
            start_scheduler()
            logger.info("Background APScheduler started successfully.")
        except Exception as e:
            logger.error(f"Failed to start background scheduler: {str(e)}")

    else:
        logger.warning("Scheduler module not found. Background jobs are disabled.")

    yield

    logger.info("Shutting Down Airport Companion API...")

    if HAS_SCHEDULER:
        try:
            shutdown_scheduler()
            logger.info("Background APScheduler shut down gracefully.")

        except Exception as e:
            logger.error(f"Error shutting down scheduler: {str(e)}")


app = FastAPI(
    title = "Autonomous Airport Terminal Companion API",
    description="Backend API for real-time passenger navigation, check-in magic links, and AI terminal assistant.",
    version = "1.0.0",
    lifespan = lifespan,
    docs_url = "/docs",
    redoc_url= "/redoc"
)

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins = allowed_origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

app.include_router(auth_routes.router)
app.include_router(flights_routes.router)
app.include_router(chat_routes.router)
app.include_router(admin_routes.router)


@app.get("/", tags = ["Health"])
async def root():
    return {
        "service" : "Airport Companion API",
        "status" : "ONLINE",
        "docs" : "Visit /docs for interactive Swagger UI",
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status":"healthy", "database":"connected"})