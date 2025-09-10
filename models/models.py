from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class UserModel(BaseModel):
    cpf: str
    senha: str
    responsavel: str


class UserPublicModel(BaseModel):
    id: int
    cpf: str
    responsavel: str


class UserListModel(BaseModel):
    users: list[UserPublicModel]


class TokenModel(BaseModel):
    access_token: str
    token_type: str
    username: str


class ArquivoEnviado(BaseModel):
    file_id: str = Field(..., description="ID único do arquivo")
    titulo_documento: str
    subgrupo: str
    grupo: str
    responsavel: str
    descricao: str
    status: str
    data_envio: datetime = Field(
        ..., description="Data e hora em que o arquivo foi enviado"
    )


class ArquivoFalhou(BaseModel):
    arquivo: str = Field(..., description="Nome do arquivo que apresentou erro")
    erro: str = Field(..., description="Descrição do erro ocorrido durante o envio")


class UploadResponse(BaseModel):
    enviados: List[ArquivoEnviado] = Field(
        ..., description="Arquivos enviados com sucesso"
    )
    falharam: List[ArquivoFalhou] = Field(
        ..., description="Arquivos que não foram processados"
    )


class CountFilesModel(BaseModel):
    legenda: str
    contagem: int


class GrupoSubgrupoModel(BaseModel):
    grupo: str
    subGrupo: str
    quantidadeDocumentos: int


class FileListModel(BaseModel):
    id: str = Field(alias="file_id")
    titulo: str = Field(alias="titulo_documento")
    grupo: str
    subgrupo: str
    status: str
    dataUpload: str = Field(alias="data_envio")

    class Config:
        populate_by_name = True  # permite usar nomes do modelo na saída


class FileUpdateMetadataModel(BaseModel):
    titulo: str
    grupo: str
    subgrupo: str
    descricao: str
    responsavel: str


class FileUpdateMetadataOutModel(BaseModel):
    id: str
    titulo: str
    grupo: str
    subgrupo: str
    descricao: str
    responsavel: str


class PaginationOutModel(BaseModel):
    page: int
    size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
    items: List[FileListModel]


class FileDetailsOutModel(BaseModel):
    id: str
    titulo: str
    grupo: str
    subgrupo: str
    descricao: str
    dataUpload: str
    responsavel: str
    descricao: str
    status: str
    nomeArquivo: str


class LastUpdateTimestampModel(BaseModel):
    data: str
    hora: str
