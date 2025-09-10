import psycopg2
import os


class DB:
    def __init__(self):
        self.connection_data = {
            "host": os.getenv("POSTGRE_HOST"),
            "database": os.getenv("POSTGRE_DATABASE"),
            "user": os.getenv("POSTGRE_USER"),
            "password": os.getenv("POSTGRE_PASSWORD"),
            "schema": os.getenv("POSTGRE_SCHEMA"),
        }

    def __exec_select__(self, select_query):
        schema_name = self.connection_data["schema"]
        conn = psycopg2.connect(
            host=self.connection_data["host"],
            database=self.connection_data["database"],
            user=self.connection_data["user"],
            password=self.connection_data["password"],
            options=f"-c search_path={schema_name}",
        )
        cursor = conn.cursor()
        cursor.execute(select_query)
        messages = cursor.fetchall()
        cursor.close()
        conn.close()

        return messages

    def __exec_insert__(self, insert_query):
        schema_name = self.connection_data["schema"]
        conn = psycopg2.connect(
            host=self.connection_data["host"],
            database=self.connection_data["database"],
            user=self.connection_data["user"],
            password=self.connection_data["password"],
            options=f"-c search_path={schema_name}",
        )
        cursor = conn.cursor()
        cursor.execute(insert_query)
        conn.commit()
        cursor.close()
        conn.close()

        return None

    def get_messages(self, number):
        select_query = f"""
            SELECT role, message
            FROM chatbot_whatsapp
            WHERE phone_number = '{number}'
            ORDER BY created_at DESC
            LIMIT 20;
        """

        return self.__exec_select__(select_query)

    def insert_message(self, number, role, message):
        insert_query = f"""
            INSERT INTO chatbot_whatsapp (phone_number, role, message)
            VALUES ('{number}', '{role}', '{message}');
        """

        return self.__exec_insert__(insert_query)

    def get_foreknowledge(self, number):
        select_query = f"""
            select general_information 
            from whatsapp_information
            where phone_number = '{number}'
        """

        foreknowledge = self.__exec_select__(select_query)
        if foreknowledge:
            return foreknowledge[0][0]
        else:
            return ""

    def update_foreknowledge(self, number, foreknowledge):
        upsert_query = f"""
            INSERT INTO whatsapp_information( phone_number, general_information )
            VALUES ('{number}', '{foreknowledge}')
            ON CONFLICT ( phone_number ) 
            DO UPDATE SET
                general_information = '{foreknowledge}';
        """

        return self.__exec_insert__(upsert_query)
