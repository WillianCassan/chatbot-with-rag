# file_manager.py
import logging
from typing import List
from fastapi import (
    Response,
    UploadFile,
    File,
    HTTPException,
    APIRouter,
    status,
    BackgroundTasks,
    Depends,
    Form,
    Query,
)
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from uuid import UUID
from minio.error import S3Error
from ..services.file_manager_service import FileManagerService
from psycopg2 import Error as Psycopg2Error
from ..security.security import get_current_user
from datetime import datetime
from ..models.models import (
    UploadResponse,
    CountFilesModel,
    GrupoSubgrupoModel,
    FileListModel,
    FileUpdateMetadataModel,
    FileUpdateMetadataOutModel,
    PaginationOutModel,
    FileDetailsOutModel,
    LastUpdateTimestampModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

logger.info("Criando instância de FileManagerService para o router /files.")
manager_service = FileManagerService()


@router.post(
    "/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    titulo_documento: str = Form(...),
    subgrupo: str = Form(...),
    grupo: str = Form(...),
    descricao: str = Form(...),
    responsavel: str = Form(...),
    current_user=Depends(get_current_user),
) -> dict:
    logger.info(f"Requisição POST /files/upload recebida para {len(files)} arquivo(s).")
    # Log dos novos metadados recebidos
    logger.info(
        f"Metadados do formulário: Titulo='{titulo_documento}', Subgrupo='{subgrupo}', "
        f"Grupo='{grupo}', Responsavel='{current_user['responsavel']}', Descricao='{descricao}'"
    )

    for f_obj in files:
        logger.debug(
            f"Arquivo recebido para upload: {f_obj.filename}, content-type: {f_obj.content_type}"
        )

    try:
        result = await manager_service.insert_files_databases(
            files,
            background_tasks,
            titulo_documento,
            subgrupo,
            grupo,
            responsavel,
            descricao,
        )

        if result is None:
            return {"message": "Erro ao enviar arquivos e metadados."}

        if result.get("falharam"):
            raise HTTPException(status_code=415, detail=result)

        logger.info(
            f"Arquivos enviados com sucesso via serviço. Quantidade: {len(files)}."
        )

        return result

    except S3Error as s3_error:
        logger.error(f"Erro S3Error ao tentar fazer upload: {s3_error}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Erro ao salvar no MinIO: {str(s3_error)}"
        )
    except HTTPException as http_exc:  # Se o serviço levantar HTTPException
        logger.warning(
            f"HTTPException durante o upload: {http_exc.status_code} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as general_error:
        logger.error(
            f"Erro geral não esperado durante o upload: {general_error}", exc_info=True
        )
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao processar a requisição: {str(general_error)}",
        )


@router.patch("/update/{file_id}", response_model=FileUpdateMetadataOutModel)
async def update_file_metadata(
    file_id: UUID,
    file_metadata: FileUpdateMetadataModel,
    current_user=Depends(get_current_user),
) -> FileUpdateMetadataOutModel:
    try:
        response = manager_service.update_file_metadata(file_id, file_metadata)

        return response
    except HTTPException as e:
        raise HTTPException(
            status_code=404, detail=f"Erro ao atualizar registro: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao atualizar registro: {str(e)}"
        )


@router.get("/download/{file_id}", response_class=StreamingResponse)
async def download_file(
    file_id: UUID, current_user=Depends(get_current_user)
) -> StreamingResponse:
    logger.info(f"Requisição GET /files/download/{file_id} recebida.")
    try:
        response_stream = manager_service.download_file(file_id)
        logger.info(f"Download do arquivo {file_id} iniciado com sucesso via serviço.")
        return response_stream
    except S3Error as error:
        logger.error(
            f"Erro S3Error ao tentar baixar o arquivo {file_id}: {error}", exc_info=True
        )
        raise HTTPException(
            status_code=404,
            detail=f"Arquivo não encontrado ou erro no MinIO: {str(error)}",
        )
    except HTTPException as http_exc:
        logger.warning(
            f"HTTPException durante o download de {file_id}: {http_exc.status_code} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Erro inesperado ao tentar baixar o arquivo {file_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Erro inesperado ao processar o download: {str(e)}"
        )


@router.get(
    "/list",
    response_model=List[FileListModel],
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
)
async def list_files(current_user=Depends(get_current_user)) -> List[FileListModel]:
    logger.info("Requisição GET /files/list recebida.")
    try:
        files_list = manager_service.get_files()

        if files_list is None:
            return []

        logger.info(f"Listagem de arquivos retornou {len(files_list)} itens.")
        return files_list
    except Exception as error:
        logger.error(f"Erro ao listar arquivos: {error}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar arquivos: {str(error)}"
        )


# @router.get(
#     "/list-paginated",
#     response_model=PaginationOutModel,
#     response_model_by_alias=False,
#     status_code=status.HTTP_200_OK,
# )
# async def list_files_paginated(
#     page: int = Query(1, ge=1),
#     size: int = Query(10, ge=1, le=100),
#     current_user=Depends(get_current_user),
# ) -> PaginationOutModel:

#     try:
#         files_list = manager_service.get_files_pagination(page=page, size=size)

#         return files_list
#     except Exception as error:
#         logger.error(f"Erro ao listar arquivos: {error}", exc_info=True)
#         raise HTTPException(
#             status_code=500, detail=f"Erro ao listar arquivos: {str(error)}"
#         )


@router.delete("/delete-file/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID, current_user=Depends(get_current_user)
) -> Response:  # Retorno Response para status_code=204
    logger.info(f"Requisição DELETE /files/delete-file/{file_id} recebida.")
    try:
        manager_service.delete_file(file_id)
        logger.info(f"Arquivo {file_id} deletado com sucesso via serviço.")
        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )  # Retornar Response com status code
    except S3Error as s3_error:
        logger.error(
            f"Erro S3Error ao tentar deletar o arquivo {file_id}: {s3_error}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=400, detail=f"Erro ao excluir no MinIO: {s3_error}"
        )
    except Psycopg2Error as pg_error:
        logger.error(
            f"Erro Psycopg2Error ao tentar deletar o arquivo {file_id}: {pg_error}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erro no banco de dados PostgreSQL: {str(pg_error)}",
        )
    except HTTPException as http_exc:
        logger.warning(
            f"HTTPException durante a deleção de {file_id}: {http_exc.status_code} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Erro inesperado ao tentar deletar o arquivo {file_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Erro inesperado: {str(e)}")


@router.get("/details/{file_id}", response_model=FileDetailsOutModel)
async def get_file_details(file_id: UUID, current_user=Depends(get_current_user)):
    logger.info(f"Requisição GET /files/{file_id}/details recebida.")
    try:
        file_details = manager_service.get_file_details_by_id(file_id)

        # O serviço deve levantar HTTPException se não encontrar, mas por segurança:
        if file_details is None:
            logger.warning(
                f"Detalhes do arquivo com ID {file_id} não encontrados pelo serviço (retornou None)."
            )
            raise HTTPException(
                status_code=404, detail="Detalhes do arquivo não encontrados"
            )

        logger.info(f"Detalhes do arquivo {file_id} recuperados com sucesso.")
        return file_details
    except HTTPException as http_exc:
        # Se o serviço já levantou uma HTTPException (ex: 404), apenas a relança
        logger.warning(
            f"HTTPException ao buscar detalhes do arquivo {file_id}: {http_exc.status_code} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Erro inesperado ao buscar detalhes do arquivo {file_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao buscar detalhes do arquivo: {str(e)}",
        )


@router.get(
    "/resume", response_model=List[CountFilesModel], status_code=status.HTTP_200_OK
)
async def get_initial_info(current_user=Depends(get_current_user)):
    try:
        info = manager_service.get_info_initial_panel()

        if info is None:
            info = []

        return info
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao buscar informações dos arquivos: {str(e)}",
        )


@router.get(
    "/resume-list",
    response_model=List[GrupoSubgrupoModel],
    status_code=status.HTTP_200_OK,
)
async def get_initial_resume_list(current_user=Depends(get_current_user)):
    try:
        info = manager_service.get_info_initial_list_panel()

        if info is None:
            info = []

        return info
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao buscar informações dos arquivos: {str(e)}",
        )


@router.get("/last_update", status_code=status.HTTP_200_OK)
async def get_last_update(
    current_user=Depends(get_current_user),
) -> LastUpdateTimestampModel:
    try:
        return manager_service.get_last_file_update()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao buscar informações dos arquivos: {str(e)}",
        )
