from fastapi import APIRouter, HTTPException, status, Depends
from http import HTTPStatus
from ..models.models import UserPublicModel, UserModel, TokenModel
from ..services.user_service import UserService
from fastapi.security import OAuth2PasswordRequestForm
from ..security.security import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/token", response_model=TokenModel)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user_service = UserService()
        return user_service.login(form_data.username, form_data.password)
    except Exception as e:
        raise


#@router.post(
#    "/register", status_code=HTTPStatus.CREATED, response_model=UserPublicModel
#)
#def create_user(user: UserModel):
#    try:
#        user_service = UserService()
#        return user_service.insert_user(user.cpf, user.senha, user.responsavel)
#    except Exception as e:
#       raise HTTPException(
#            status_code=status.HTTP_409_CONFLICT, detail="Usuário já cadastrado"
#        )
