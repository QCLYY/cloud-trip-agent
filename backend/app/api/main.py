from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.export import router as export_router
from app.api.routes.memory import router as memory_router
from app.api.routes.trip import router as trip_router
from app.api.routes.weather import router as weather_router


app = FastAPI(
    title="Trip Planner Demo Backend",
    description="MVP backend for the intelligent travel assistant.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize_validation_error(error: dict) -> dict:
    """避免认证请求校验失败时把 password 输入值回显给客户端。"""
    sanitized = dict(error)
    loc = sanitized.get("loc") or ()
    if any(str(part) == "password" for part in loc):
        sanitized.pop("input", None)
    return sanitized


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                _sanitize_validation_error(error)
                for error in exc.errors()
            ]
        },
    )


@app.get("/")
def read_root() -> dict[str, str]:
    """根路径接口，用于确认后端服务已启动。"""
    return {"message": "Trip Planner Demo backend is running."}


@app.get("/health")
def health_check() -> dict[str, str]:
    """健康检查接口。"""
    return {"status": "ok"}


app.include_router(trip_router)
app.include_router(export_router)
app.include_router(weather_router)
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(confirmations_router)
app.include_router(assistant_router)
