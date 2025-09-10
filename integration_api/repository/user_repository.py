import os
import psycopg2


class UserRepository:
    def __init__(self):
        self.host = os.getenv("POSTGRE_HOST")
        self.database = os.getenv("POSTGRE_DATABASE")
        self.user = os.getenv("POSTGRE_USER")
        self.password = os.getenv("POSTGRE_PASSWORD")
        self.port = os.getenv("POSTGRE_PORT")
        self.schema = os.getenv("POSTGRE_SCHEMA")

    def __get_connection(self):
        return psycopg2.connect(
            database=self.database,
            user=self.user,
            host=self.host,
            password=self.password,
            port=self.port,
            options=f"-c search_path={self.schema}",
        )

    def insert_user(self, cpf: str, senha: str, responsavel: str):
        conn = self.__get_connection()

        cur = conn.cursor()

        cur.execute("SELECT 1 FROM users WHERE cpf = %s", (cpf,))

        if cur.fetchone():
            cur.close()
            conn.close()
            raise Exception("Usuário já existe")

        cur.execute(
            "INSERT INTO users (cpf, senha, responsavel) VALUES (%s, %s, %s) RETURNING id, cpf, responsavel",
            (cpf, senha, responsavel),
        )

        user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return user

    def get_user(self, cpf: str):
        conn = self.__get_connection()

        cur = conn.cursor()
        cur.execute(
            "SELECT id, cpf, senha, responsavel FROM users WHERE cpf = %s LIMIT 1",
            (cpf,),
        )
        exists = cur.fetchone()
        cur.close()
        conn.close()

        return exists