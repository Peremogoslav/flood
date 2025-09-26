from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
import json
from pathlib import Path
from ..settings import settings
from ..security import bearer_auth, get_current_user_id
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import UserConfig

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
def get_config(current_user_id: int = Depends(get_current_user_id(settings.jwt_secret)), db: Session = Depends(get_db)):
    rec = db.query(UserConfig).filter_by(user_id=current_user_id).first()
    if not rec:
        rec = UserConfig(user_id=current_user_id, min_delay=DEFAULT_CONFIG.min_delay, max_delay=DEFAULT_CONFIG.max_delay, randomize_chats=1 if DEFAULT_CONFIG.randomize_chats else 0, use_images=1 if DEFAULT_CONFIG.use_images else 0)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return ConfigModel(min_delay=rec.min_delay, max_delay=rec.max_delay, randomize_chats=bool(rec.randomize_chats), use_images=bool(rec.use_images))


@router.put("/", response_model=ConfigModel)
def update_config(cfg: ConfigModel, current_user_id: int = Depends(get_current_user_id(settings.jwt_secret)), db: Session = Depends(get_db)):
    rec = db.query(UserConfig).filter_by(user_id=current_user_id).first()
    if not rec:
        rec = UserConfig(user_id=current_user_id)
        db.add(rec)
    rec.min_delay = cfg.min_delay
    rec.max_delay = cfg.max_delay
    rec.randomize_chats = 1 if cfg.randomize_chats else 0
    rec.use_images = 1 if (cfg.use_images or False) else 0
    db.commit()
    return cfg

