import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from http import HTTPStatus

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidSignatureError,
    encode,
    decode,
)
from jwt.exceptions import PyJWTError
from ..repository.user_repository import UserRepository
import os


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AuthSecurity")
# --- Fim da Configuração do Logging ---

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/users/token",
    scheme_name="JWT"
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES_STR = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")


if not SECRET_KEY:
    logger.critical(
        "Variável de ambiente SECRET_KEY não definida! A autenticação JWT não funcionará."
    )

if not ALGORITHM:
    logger.critical(
        "Variável de ambiente ALGORITHM não definida! A autenticação JWT não funcionará."
    )


ACCESS_TOKEN_EXPIRE_MINUTES = 30
if ACCESS_TOKEN_EXPIRE_MINUTES_STR:
    try:
        ACCESS_TOKEN_EXPIRE_MINUTES = int(ACCESS_TOKEN_EXPIRE_MINUTES_STR)
        logger.info(
            f"Tempo de expiração do token de acesso definido para: {ACCESS_TOKEN_EXPIRE_MINUTES} minutos."
        )
    except ValueError:
        logger.error(
            f"Valor inválido para ACCESS_TOKEN_EXPIRE_MINUTES: '{ACCESS_TOKEN_EXPIRE_MINUTES_STR}'. "
            f"Usando valor padrão: {ACCESS_TOKEN_EXPIRE_MINUTES} minutos."
        )
else:
    logger.warning(
        f"Variável de ambiente ACCESS_TOKEN_EXPIRE_MINUTES não definida. "
        f"Usando valor padrão: {ACCESS_TOKEN_EXPIRE_MINUTES} minutos."
    )


def create_access_token(data: dict):
    if not SECRET_KEY or not ALGORITHM:
        logger.error(
            "Falha ao criar token de acesso: SECRET_KEY ou ALGORITHM não configurados."
        )

        raise ValueError("Configuração de servidor inválida para criação de token.")

    to_encode = data.copy()
    subject = to_encode.get("sub", "N/A")
    logger.info(f"Criando token de acesso para o sujeito (sub): {subject}")

    try:
        expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
        logger.debug(
            f"Token para '{subject}' irá expirar em (UTC): {expire.isoformat()}"
        )
    except Exception as e:
        logger.error(
            f"Erro ao calcular a data de expiração do token para '{subject}': {e}",
            exc_info=True,
        )
        raise ValueError("Erro ao calcular expiração do token.")

    to_encode.update({"exp": int(expire.timestamp())})

    try:
        encoded_jwt = encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Token de acesso codificado com sucesso para o sujeito: {subject}")
        return encoded_jwt
    except PyJWTError as e:
        logger.error(
            f"Erro ao codificar JWT para o sujeito '{subject}': {e}", exc_info=True
        )

        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Não foi possível criar o token de acesso.",
        )


def get_current_user(token: str = Depends(oauth2_scheme)):
    logger.debug("Tentando obter usuário atual a partir do token.")

    if not SECRET_KEY or not ALGORITHM:
        logger.error(
            "Falha ao validar token: SECRET_KEY ou ALGORITHM não configurados."
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Configuração de segurança do servidor incompleta.",
        )

    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_exp = payload.get("exp")

        if token_exp:
            exp_datetime = datetime.fromtimestamp(token_exp, tz=ZoneInfo("UTC"))
            logger.debug(
                f"Payload do token decodificado. Usuário (sub): {username}, Expira em (UTC): {exp_datetime.isoformat()}"
            )
        else:
            logger.debug(
                f"Payload do token decodificado. Usuário (sub): {username}. Sem campo 'exp'."
            )

        if username is None:
            logger.warning(
                "Token decodificado com sucesso, mas o campo 'sub' (username) está ausente."
            )
            raise credentials_exception

        logger.info(f"Token validado com sucesso para o usuário: {username}")

    except ExpiredSignatureError:
        logger.warning("Falha na validação do token: Token expirado.")
        raise credentials_exception
    except InvalidSignatureError:
        logger.warning("Falha na validação do token: Assinatura inválida.")
        raise credentials_exception
    except DecodeError as e:
        logger.warning(
            f"Falha na validação do token: Erro ao decodificar. Detalhes: {e}"
        )
        raise credentials_exception
    except PyJWTError as e:
        logger.error(
            f"Erro inesperado na biblioteca PyJWT ao validar o token: {e}",
            exc_info=True,
        )
        raise credentials_exception
    except Exception as e:
        logger.error(
            f"Erro inesperado durante o processamento do token: {e}", exc_info=True
        )
        raise credentials_exception

    # Se chegou até aqui, o payload foi decodificado e o username (sub) está presente
    try:
        repository = UserRepository()
        user = repository.get_user(username)
        if user is None:
            logger.warning(
                f"Usuário '{username}' (do token) não encontrado no repositório."
            )
            raise credentials_exception

        logger.info(f"Usuário '{username}' recuperado com sucesso do repositório.")

        return {"id": user[0], "usuario": user[1], "responsavel": user[3]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erro ao buscar ou processar dados do usuário '{username}' do repositório: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Erro ao recuperar informações do usuário.",
        )
