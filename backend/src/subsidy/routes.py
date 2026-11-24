from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import current_user, require_roles
from ..database import get_db
from ..models import User
from . import service
from .schemas import ConfigureSubsidy

router = APIRouter(prefix='/subsidy-pool', tags=['周末试行补贴'])


@router.get('')
def pool(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return service.pool_json(service.get_pool(db))


@router.put('')
def configure(payload: ConfigureSubsidy, db: Session = Depends(get_db),
              user: User = Depends(require_roles('revenue', 'admin'))):
    result = service.configure(db, payload, user)
    db.commit()
    return result
