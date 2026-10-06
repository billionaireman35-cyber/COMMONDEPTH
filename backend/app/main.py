from fastapi import FastAPI

from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.auth import router as auth_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.posts import router as posts_router
from app.api.v1.social import router as social_router
from app.api.v1.feed import router as feed_router
from app.api.v1.discover import router as discover_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    profiles_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    social_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    posts_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    feed_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    discover_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    onboarding_router,
    prefix=settings.api_v1_prefix,
)
