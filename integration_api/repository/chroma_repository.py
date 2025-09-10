from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
import io
from ..repository.postgre_repository import PostgreRepository
from uuid import UUID
import chromadb
import fitz  # PyMuPDF
import os


class ChromaRepository:
    STATUS_FINALIZADO = "Finalizado"
    STATUS_ERRO = "Erro"
    STATUS_PROCESSANDO = "Processando"

    def __init__(self):
        self.client = None
        self.collection = None
        self.postgre = PostgreRepository()
        self._initialized = False

    def _ensure_initialized(self):
        """Inicializa o cliente ChromaDB apenas quando necessário"""
        if not self._initialized:
            chroma_host = os.getenv("CHROMADB_HOST")
            chroma_port = os.getenv("CHROMADB_PORT")
            chroma_collection = os.getenv("CHROMADB_COLLECTION")
            
            if not all([chroma_host, chroma_port, chroma_collection]):
                raise ValueError("Variáveis de ambiente ChromaDB não configuradas corretamente")
            
            self.client = chromadb.HttpClient(
                host=chroma_host, port=chroma_port
            )
            self.collection = self.client.get_or_create_collection(
                name=chroma_collection
            )
            self._initialized = True

    def __extract_text_from_uploadfile(self, filename: str, contents: bytes):
        """Extrai e retorna texto de todos os arquivos suportados"""
        all_texts = {}

        try:
            if not contents:
                raise ValueError(f"O arquivo {filename} está vazio.")

            text = ""

            if filename.endswith(".txt"):
                text = contents.decode("utf-8")
            elif filename.endswith(".pdf"):
                pdf_stream = io.BytesIO(contents)
                with fitz.open(stream=pdf_stream, filetype="pdf") as pdf:
                    for page in pdf:
                        text += page.get_text("text") + "\n"
            else:
                raise ValueError("Tipo de arquivo não suportado")

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=250,
                chunk_overlap=20,
                separators=["\n\n", "\n", " ", ""],
            )

            chunks = splitter.split_text(text)

            for i, chunk in enumerate(chunks):
                all_texts[f"{filename}_chunk_{i}"] = chunk

        except Exception as e:
            print(f"Erro ao processar {filename}: {e}")

        return all_texts

    def index_new_documents(self, file_id: UUID, filename: str, contents: bytes):
        self._ensure_initialized()
        new_documents = self.__extract_text_from_uploadfile(filename, contents)

        for doc_id, text in new_documents.items():
            self.collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[{"file_id": str(file_id), "filename": filename}],
            )

        self.postgre.update_status(file_id, self.STATUS_FINALIZADO)

    def delete_document_chroma(self, file_id: UUID):
        self._ensure_initialized()
        self.collection.delete(where={"file_id": str(file_id)})
