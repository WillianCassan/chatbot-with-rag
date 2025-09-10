import os
import psycopg2
from uuid import UUID
from typing import Dict, Any
from psycopg2.extras import RealDictCursor
from ..models.models import PaginationOutModel, FileListModel


class PostgreRepository:
    def __init__(self):
        self.host = None
        self.database = None
        self.user = None
        self.password = None
        self.port = None
        self.schema = None
        self._initialized = False

    def _ensure_initialized(self):
        """Inicializa as configurações apenas quando necessário"""
        if not self._initialized:
            self.host = os.getenv("POSTGRE_HOST")
            self.database = os.getenv("POSTGRE_DATABASE")
            self.user = os.getenv("POSTGRE_USER")
            self.password = os.getenv("POSTGRE_PASSWORD")
            self.port = os.getenv("POSTGRE_PORT")
            self.schema = os.getenv("POSTGRE_SCHEMA")
            
            if not all([self.host, self.database, self.user, self.password, self.port, self.schema]):
                raise ValueError("Variáveis de ambiente PostgreSQL não configuradas corretamente")
            
            self._initialized = True

    def __get_connection(self):
        self._ensure_initialized()
        return psycopg2.connect(
            database=self.database,
            user=self.user,
            host=self.host,
            password=self.password,
            port=self.port,
            options=f"-c search_path={self.schema}",
        )

    def insert_index(
        self,
        file_id: str,
        filename: str,
        minio_object_name: str,
        file_hash: str,
        titulo_documento: str,
        subgrupo: str,
        grupo: str,
        responsavel: str,
        descricao: str,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        query = f"""
            INSERT INTO {self.schema}.indexed_documents (
                file_id, filename, minio_object_name, file_hash,
                titulo_documento, subgrupo, grupo, responsavel, descricao
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING file_id, titulo_documento, subgrupo, grupo, responsavel, descricao, status, data_envio
        """
        values = (
            file_id,
            filename,
            minio_object_name,
            file_hash,
            titulo_documento,
            subgrupo,
            grupo,
            responsavel,
            descricao,
        )
        with self.__get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)
                row = cur.fetchone()
                colnames = [desc[0] for desc in cur.description]
                return dict(zip(colnames, row))

    def update_index(
        self,
        file_id: str,
        titulo: str,
        grupo: str,
        subgrupo: str,
        descricao: str,
        responsavel: str,
    ):
        try:
            self._ensure_initialized()
            sql_query = f"""UPDATE {self.schema}.indexed_documents
                           SET titulo_documento = %s, grupo = %s, subgrupo = %s, descricao = %s, responsavel = %s
                           WHERE file_id = %s
                           RETURNING file_id, titulo_documento, grupo, subgrupo, descricao, responsavel
            """
            values = (titulo, grupo, subgrupo, descricao, responsavel, file_id)
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_query, values)
                    updated = cur.fetchone()
                    return updated
        except Exception as e:
            raise

    def delete_index(self, file_id: UUID):
        self._ensure_initialized()
        conn = self.__get_connection()
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM {self.schema}.indexed_documents WHERE file_id = '{str(file_id)}'"
        )  # ALERTA: SQL Injection
        conn.commit()
        cur.close()
        conn.close()

    def is_indexed_hash(self, hash):
        self._ensure_initialized()
        conn = self.__get_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT 1 FROM {self.schema}.indexed_documents WHERE file_hash = %s LIMIT 1", (hash,)
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists

    def is_indexed_uuid(self, file_id):
        self._ensure_initialized()
        conn = self.__get_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT file_id, minio_object_name FROM {self.schema}.indexed_documents WHERE file_id = %s LIMIT 1",
            (file_id,),
        )
        exists = cur.fetchone()
        cur.close()
        conn.close()
        return exists

    def get_all_files(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT
                            file_id, titulo_documento, grupo, subgrupo, status, data_envio
                        FROM {self.schema}.indexed_documents
                        ORDER BY titulo_documento, grupo, subgrupo
                        """
                    )
                    results = cur.fetchall()
                    return [
                        {
                            "id": row[0],
                            "titulo": row[1],
                            "grupo": row[2],
                            "subgrupo": row[3],
                            "status": row[4],
                            "dataUpload": row[5],
                        }
                        for row in results
                    ]
        except Exception as e:
            raise

    def get_all_files_pagination(self, page: int, size: int):
        offset = (page - 1) * size
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {self.schema}.indexed_documents")
                    total = cur.fetchone()["count"]
                    cur.execute(
                        f"""
                            SELECT
                                file_id, titulo_documento, grupo, subgrupo, status, TO_CHAR(data_envio, 'YYYY-MM-DD') AS data_envio
                            FROM {self.schema}.indexed_documents
                            ORDER BY data_envio DESC, titulo_documento ASC -- Adicionada ordenação para paginação consistente
                            LIMIT %s OFFSET %s
                        """,
                        (size, offset),
                    )
                    results = cur.fetchall()
                    return PaginationOutModel(
                        page=page,
                        size=size,
                        total=total,
                        total_pages=(total + size - 1) // size if size > 0 else 0,
                        has_next=(offset + len(results)) < total,
                        has_previous=page > 1,
                        items=[FileListModel(**row) for row in results],
                    )
        except Exception as e:
            raise

    def update_status(self, file_id: str, status: str):
        self._ensure_initialized()
        conn = self.__get_connection()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {self.schema}.indexed_documents SET status = '{status}' WHERE file_id = '{file_id}'"
        )
        conn.commit()
        cur.close()
        conn.close()

    def get_file_details_from_db(self, file_id_str: str):
        self._ensure_initialized()
        conn = None
        cur = None
        try:
            conn = self.__get_connection()
            cur = conn.cursor()
            sql_query = f"""
                SELECT
                    file_id, titulo_documento, grupo, subgrupo, descricao, TO_CHAR(data_envio, 'YYYY-MM-DD'), responsavel, status, filename
                FROM
                    {self.schema}.indexed_documents
                WHERE
                    file_id = %s
            """

            values = (file_id_str,)
            cur.execute(sql_query, values)
            row = cur.fetchone()
            if row:
                return row
            else:
                return None
        except psycopg2.Error as e:
            raise
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def __get_registered_files_count(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {self.schema}.indexed_documents")
                    total = cur.fetchone()[0]
                    return total
        except Exception as e:
            raise

    def __get_groups_count(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(DISTINCT grupo) FROM {self.schema}.indexed_documents"
                    )
                    total = cur.fetchone()[0]
                    return total
        except Exception as e:
            raise

    def __get_subgroups_count(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(DISTINCT subgrupo) FROM {self.schema}.indexed_documents"
                    )
                    total = cur.fetchone()[0]
                    return total
        except Exception as e:
            raise

    def get_info_initial_panel(self):
        self._ensure_initialized()
        num_files = self.__get_registered_files_count()
        num_groups = self.__get_groups_count()
        num_subgroups = self.__get_subgroups_count()
        return [
            {"legenda": "Arquivos Cadastrados", "contagem": num_files},
            {"legenda": "Grupos Cadastrados", "contagem": num_groups},
            {"legenda": "Subgrupos Cadastrados", "contagem": num_subgroups},
        ]

    def get_list_info_initial_panel(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT
                            grupo,
                            subgrupo AS "subGrupo",
                            COUNT(*) AS "quantidadeDocumentos"
                        FROM {self.schema}.indexed_documents
                        GROUP BY grupo, subgrupo
                        ORDER BY grupo, subgrupo;
                        """
                    )
                    results = cur.fetchall()
                    return [
                        {
                            "grupo": row[0],
                            "subGrupo": row[1],
                            "quantidadeDocumentos": row[2],
                        }
                        for row in results
                    ]
        except Exception as e:
            raise

    def get_last_update(self):
        try:
            self._ensure_initialized()
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT data_envio FROM {self.schema}.indexed_documents ORDER BY data_envio DESC LIMIT 1"
                    )
                    last_update = cur.fetchone()
                    return last_update
        except Exception as e:
            raise
