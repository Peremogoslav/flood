from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "error": "validation_error",
        "details": exc.errors()
    })


async def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={
        "error": "conflict",
        "details": str(exc.orig) if exc.orig else str(exc)
    })


async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "error": "internal_error",
        "details": "Unexpected server error"
    })

