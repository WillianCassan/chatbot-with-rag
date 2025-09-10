import logging
from ..repository.user_repository import UserRepository
from passlib.context import CryptContext
from fastapi import HTTPException, status
from ..security.security import create_access_token
import re


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("UserService")


class UserService:
    def __init__(self):
        self.postgre = UserRepository()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        logger.info("Instância de UserService criada.")

    def insert_user(self, cpf: str, senha: str, responsavel: str):
        logger.info(f"Tentativa de inserção de usuário com CPF: {cpf}")
        try:
            password_hash = self.__get_password_hash(senha)
            logger.debug(f"Hash da senha gerado para CPF: {cpf}")

            registered_user = self.postgre.insert_user(cpf, password_hash, responsavel)

            if registered_user is not None:
                user_id = registered_user[0]
                logger.info(
                    f"Usuário com CPF: {cpf} registrado com sucesso. ID: {user_id}"
                )
                return {
                    "id": user_id,
                    "cpf": registered_user[1],
                    "responsavel": registered_user[2],
                }
            else:
                logger.warning(
                    f"Falha ao registrar usuário com CPF: {cpf}. Usuário pode já existir ou repositório retornou None."
                )
                raise HTTPException(status_code=409, detail="Usuário já cadastrado")
        except HTTPException as http_exc:

            raise http_exc
        except Exception as e:
            logger.error(
                f"Erro inesperado ao inserir usuário com CPF {cpf}: {e}", exc_info=True
            )

            raise HTTPException(
                status_code=500,
                detail="Ocorreu um erro interno ao tentar registrar o usuário.",
            )

    def login(self, cpf: str, senha: str):
        logger.info(f"Tentativa de login para o CPF: {cpf}")

        if not cpf or not cpf.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dados inválidos! Revise e tente novamente.",
            )

        if not senha or not senha.strip() or len(senha) < 8:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dados inválidos! Revise e tente novamente.",
            )

        cpf_is_valid = self.__verify_cpf(cpf)

        if not cpf_is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CPF inválido!",
            )

        try:
            user = self.postgre.get_user(cpf)

            if not user:
                logger.warning(f"Falha no login: Usuário com CPF {cpf} não encontrado.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Dados inválidos! Revise e tente novamente.",
                )

            hashed_password = user[2]
            saved_cpf = user[1]
            username = user[3]

            if not self.__verify_password(senha, hashed_password):
                logger.warning(f"Falha no login: Senha inválida para o CPF {cpf}.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Dados inválidos! Revise e tente novamente.",
                )

            access_token = create_access_token(data={"sub": saved_cpf})
            logger.info(
                f"Login bem-sucedido para o CPF: {cpf}. Token de acesso gerado."
            )

            return {
                "access_token": access_token,
                "token_type": "Bearer",
                "username": username,
            }
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.error(
                f"Erro inesperado durante o login para o CPF {cpf}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Ocorreu um erro interno ao tentar fazer login."
            )

    def __get_password_hash(self, password: str) -> str:

        return self.pwd_context.hash(password)

    def __verify_password(self, password: str, hashed: str) -> bool:

        return self.pwd_context.verify(password, hashed)

    def __verify_cpf(self, cpf: str) -> bool:
        # Remove caracteres que não são dígitos
        cpf = re.sub(r"\D", "", cpf)

        # CPF deve ter 11 dígitos e não pode ser uma sequência repetida
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        # Calcula o primeiro dígito verificador
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = (soma * 10) % 11
        if digito1 == 10:
            digito1 = 0

        # Calcula o segundo dígito verificador
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = (soma * 10) % 11
        if digito2 == 10:
            digito2 = 0

        # Verifica se os dígitos calculados conferem com os do CPF
        return cpf[-2:] == f"{digito1}{digito2}"
