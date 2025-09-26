from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
import json
from pathlib import Path
from ..settings import settings
from ..security import bearer_auth

CONFIG_PATH = Path("spam_config.json")


class ConfigModel(BaseModel):
    min_delay: int = Field(ge=1, le=3600)
    max_delay: int = Field(ge=1, le=3600)
    randomize_chats: bool
    use_images: bool | None = False

    @model_validator(mode="after")
    def validate_range(self):
        if self.max_delay < self.min_delay:
            raise ValueError("max_delay must be >= min_delay")
        return self


DEFAULT_CONFIG = ConfigModel(
    min_delay=10,
    max_delay=15,
    randomize_chats=True,
    use_images=False,
)


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


@router.get("/", response_model=ConfigModel)
def get_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(DEFAULT_CONFIG.model_dump_json(ensure_ascii=False, indent=4), encoding="utf-8")
        return DEFAULT_CONFIG
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return ConfigModel(**{**DEFAULT_CONFIG.model_dump(), **data})
    except Exception:
        CONFIG_PATH.write_text(DEFAULT_CONFIG.model_dump_json(ensure_ascii=False, indent=4), encoding="utf-8")
        return DEFAULT_CONFIG


@router.put("/", response_model=ConfigModel)
def update_config(cfg: ConfigModel):
    CONFIG_PATH.write_text(cfg.model_dump_json(ensure_ascii=False, indent=4), encoding="utf-8")
    return cfg

