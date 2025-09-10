import logging
from typing import List
from ..repository.minio_repository import MinioRepository
from ..repository.postgre_repository import PostgreRepository
from ..repository.chroma_repository import ChromaRepository
from zoneinfo import ZoneInfo
import hashlib
from fastapi import UploadFile, HTTPException, BackgroundTasks, Response, status
import uuid
from uuid import UUID
import io
from ..models.models import (
    FileUpdateMetadataModel,
    FileDetailsOutModel,
    LastUpdateTimestampModel,
)

logger = logging.getLogger(__name__)


class FileManagerService:
    def __init__(self):
        self.minio = MinioRepository()
        self.postgre = PostgreRepository()
        self.chroma = ChromaRepository()
        logger.info(
            "FileManagerService inicializado com os repositórios Minio, Postgre e Chroma."
        )

    async def insert_files_databases(
        self,
        files: List[UploadFile],
        background_tasks: BackgroundTasks,
        titulo_documento: str,
        subgrupo: str,
        grupo: str,
        responsavel: str,
        descricao: str,
    ):
        logger.info(
            f"Iniciando a inserção de {len(files)} arquivo(s) nas bases de dados."
        )

        for file in files:
            if not file.filename and file.filename.strip() == "":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nenhum arquivo enviado",
                )

        if not titulo_documento or not titulo_documento.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'titulo_documento' não pode estar vazio.",
            )
        if not subgrupo or not subgrupo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'subgrupo' não pode estar vazio.",
            )
        if not grupo or not grupo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'grupo' não pode estar vazio.",
            )
        if not descricao or not descricao.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'descricao' não pode estar vazio ou conter apenas espaços.",
            )
        if not responsavel or not responsavel.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'responsavel' não pode estar vazio ou conter apenas espaços.",
            )

        sent = []
        failed = []

        MAX_SIZE_MB = 10  # por exemplo, 5 MB
        MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

        for file in files:
            try:
                logger.debug(f"Processando arquivo: {file.filename}")
                await file.seek(0)
                file_bytes = await file.read()

                file_size = len(file_bytes)

                if not file.filename.endswith((".pdf", ".txt")):
                    logger.warning(f"O arquivo {file.filename} não é suportado.")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tipo de arquivo não suportado.",
                    )

                if file_size > MAX_SIZE_BYTES:
                    logger.warning(
                        f"O arquivo {file.filename} excedeu o tamanho máximo de 10MB."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tamanho máximo do arquivo excedido.",
                    )

                if not file_bytes:
                    logger.warning(f"O arquivo {file.filename} está vazio.")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Arquivo enviado está vazio.",
                    )

                file_stream = io.BytesIO(file_bytes)
                logger.debug(f"Arquivo {file.filename} lido em memória.")

                file_hash = self.__calculate_hash_file(file_bytes)
                logger.info(f"Hash SHA256 calculado para {file.filename}: {file_hash}")

                if not self.__document_is_indexed(file_hash):
                    logger.info(
                        f"Documento com hash {file_hash} ({file.filename}) não está indexado. Prosseguindo com a inserção."
                    )
                    generated_uuid_str = (
                        self.__generate_uuid()
                    )  # Captura o UUID como string
                    logger.info(
                        f"UUID gerado para {file.filename}: {generated_uuid_str}"
                    )

                    minio_object_name = f"{generated_uuid_str}_{file.filename}"

                    # insere no minio
                    logger.debug(
                        f"Fazendo upload de {file.filename} para MinIO como {minio_object_name}"
                    )
                    await self.minio.upload_file(minio_object_name, file_stream)
                    logger.info(
                        f"Arquivo {minio_object_name} enviado para o MinIO com sucesso."
                    )
                    # insere os metadados no postgre
                    logger.debug(
                        f"Inserindo metadados de {file.filename} (UUID: {generated_uuid_str}) no PostgreSQL."
                    )

                    file_uploaded_info = self.postgre.insert_index(
                        generated_uuid_str,
                        file.filename,
                        minio_object_name,
                        file_hash,
                        titulo_documento,
                        subgrupo,
                        grupo,
                        responsavel,
                        descricao,
                    )

                    logger.info(
                        f"Metadados de {file.filename} (UUID: {generated_uuid_str}) inseridos no PostgreSQL."
                    )

                    # insere no chromadb
                    logger.debug(
                        f"Adicionando tarefa em background para indexar {file.filename} (UUID: {generated_uuid_str}) no ChromaDB."
                    )
                    background_tasks.add_task(
                        self.chroma.index_new_documents,
                        UUID(generated_uuid_str),
                        file.filename,
                        file_bytes,
                    )

                    sent.append(file_uploaded_info)

                    logger.info(
                        f"Tarefa para indexação de {file.filename} no ChromaDB adicionada."
                    )
                else:
                    logger.warning(
                        f"Arquivo {file.filename} com hash {file_hash} já existente na base de dados. Upload cancelado."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="O arquivo já foi enviado anteriormente, selecione um novo arquivo e tente novamente.",
                    )
            except Exception as e:
                failed.append({"arquivo": file.filename, "erro": str(e.detail)})

        logger.info(f"Processo de inserção de {len(files)} arquivo(s) concluído.")

        return {"enviados": sent, "falharam": failed}

    def update_file_metadata(
        self, file_id: UUID, file_metadata: FileUpdateMetadataModel
    ):
        if not file_metadata.titulo or not file_metadata.titulo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'titulo_documento' não pode estar vazio.",
            )

        if not file_metadata.subgrupo or not file_metadata.subgrupo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'subgrupo' não pode estar vazio.",
            )

        if not file_metadata.grupo or not file_metadata.grupo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'grupo' não pode estar vazio.",
            )
        if not file_metadata.descricao or not file_metadata.descricao.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'descricao' não pode estar vazio.",
            )
        if not file_metadata.responsavel or not file_metadata.responsavel.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O campo 'responsavel' não pode estar vazio.",
            )

        updated_file_metadata = self.postgre.update_index(
            str(file_id),
            file_metadata.titulo,
            file_metadata.grupo,
            file_metadata.subgrupo,
            file_metadata.descricao,
            file_metadata.responsavel,
        )

        if updated_file_metadata is not None:
            return {
                "id": updated_file_metadata[0],
                "titulo": updated_file_metadata[1],
                "grupo": updated_file_metadata[2],
                "subgrupo": updated_file_metadata[3],
                "descricao": updated_file_metadata[4],
                "responsavel": updated_file_metadata[5],
            }
        else:
            raise HTTPException(status_code=404, detail="Metadado não encontrado")

    def delete_file(self, file_id: UUID):
        logger.info(f"Tentando deletar arquivo com UUID: {file_id}")
        file_information = self.postgre.is_indexed_uuid(file_id=str(file_id))
        if file_information is not None:
            minio_object_name = file_information[1]
            logger.debug(
                f"Arquivo encontrado no Postgre. Nome no MinIO: {minio_object_name}"
            )

            # remove do MinIO
            logger.debug(f"Removendo {minio_object_name} do MinIO.")
            self.minio.delete_file(minio_object_name)
            logger.info(f"Arquivo {minio_object_name} removido do MinIO.")

            # remove do ChromaDB
            logger.debug(f"Removendo documento com UUID {file_id} do ChromaDB.")
            self.chroma.delete_document_chroma(file_id)
            logger.info(f"Documento com UUID {file_id} removido do ChromaDB.")

            # remove do PostGre
            logger.debug(f"Removendo índice com UUID {file_id} do PostgreSQL.")
            self.postgre.delete_index(file_id)
            logger.info(f"Índice com UUID {file_id} removido do PostgreSQL.")
        else:
            logger.warning(f"Arquivo com UUID {file_id} não encontrado para deleção.")
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    def get_files(self):
        logger.info("Buscando todos os arquivos indexados no PostgreSQL.")
        files = self.postgre.get_all_files()

        for file in files:
            timestamp = file["dataUpload"]
            timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
            timestamp = timestamp.astimezone(ZoneInfo("America/Fortaleza"))

            formatted_date = timestamp.strftime("%Y-%m-%d")
            file["dataUpload"] = formatted_date

        logger.info(f"Encontrados {len(files)} arquivos.")
        return files

    def get_files_pagination(self, page: int, size: int):
        files = self.postgre.get_all_files_pagination(page, size)

        return files

    def download_file(self, file_id: UUID):
        logger.info(f"Tentando baixar arquivo com UUID: {file_id}")
        is_index = self.postgre.is_indexed_uuid(str(file_id))
        if is_index is not None:
            minio_object_name = is_index[1]
            logger.debug(
                f"Arquivo com UUID {file_id} encontrado. Nome no MinIO: {minio_object_name}. Iniciando download."
            )
            file_data = self.minio.download_file(filename=minio_object_name)
            logger.info(
                f"Download do arquivo {minio_object_name} (UUID: {file_id}) iniciado."
            )
            return file_data
        else:
            logger.warning(f"Arquivo com UUID {file_id} não encontrado para download.")
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    def __document_is_indexed(self, hash_value: str) -> bool:
        logger.debug(
            f"Verificando no PostgreSQL se o hash {hash_value} já está indexado."
        )
        is_indexed = self.postgre.is_indexed_hash(hash_value)
        logger.debug(
            f"Resultado da verificação de indexação para hash {hash_value}: {is_indexed}"
        )
        return is_indexed

    def __calculate_hash_file(self, content: bytes) -> str:
        hasher = hashlib.sha256()
        hasher.update(content)
        file_hash = hasher.hexdigest()
        return file_hash

    def __generate_uuid(self) -> str:
        new_uuid = str(uuid.uuid4())
        return new_uuid

    def get_file_details_by_id(self, file_id: UUID):
        logger.info(f"Buscando detalhes do arquivo com UUID: {file_id} no serviço.")

        file_data = self.postgre.get_file_details_from_db(str(file_id))

        if file_data is None:
            logger.warning(
                f"Detalhes do arquivo com UUID {file_id} não encontrados no banco de dados."
            )
            raise HTTPException(
                status_code=404,
                detail="Arquivo não encontrado ou detalhes indisponíveis",
            )

        logger.debug(f"Dados brutos do arquivo {file_id} do repositório: {file_data}")

        if isinstance(file_data, tuple):
            # Verifique a ordem das colunas query SQL no repositório

            details_dict = {
                "id": str(file_data[0]),
                "titulo": file_data[1],
                "grupo": file_data[2],
                "subgrupo": file_data[3],
                "descricao": file_data[4],
                "dataUpload": file_data[5],
                "responsavel": file_data[6],
                "status": file_data[7],
                "nomeArquivo": file_data[8],
            }

            return details_dict
        elif isinstance(file_data, dict):
            return file_data

        logger.error(
            f"Formato de dados inesperado recebido do repositório para file_id {file_id}: {type(file_data)}"
        )
        raise HTTPException(
            status_code=500, detail="Erro interno ao processar detalhes do arquivo."
        )

    def get_info_initial_panel(self):
        return self.postgre.get_info_initial_panel()

    def get_info_initial_list_panel(self):
        return self.postgre.get_list_info_initial_panel()

    def get_last_file_update(self):

        result = self.postgre.get_last_update()

        if result is None:
            return Response(status_code=204)

        timestamp = result[0]

        # Converter para fuso horário local
        timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
        timestamp = timestamp.astimezone(ZoneInfo("America/Fortaleza"))

        formatted_date = timestamp.strftime("%d/%m/%Y")
        formatted_hour = timestamp.strftime("%H:%M")

        date = LastUpdateTimestampModel(data=formatted_date, hora=formatted_hour)

        return date
