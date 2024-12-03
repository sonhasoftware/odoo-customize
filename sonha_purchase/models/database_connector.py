import psycopg2
from odoo import models, _
from odoo.exceptions import UserError


class DatabaseConnector(models.Model):
    _name = "external.db.connector"
    _description = "Database Connector"

    def connect_to_external_db(self):
        db_host = "10.254.0.3"
        db_port = "5432"
        db_name = "eservices.sonha.com.vn"
        db_user = "postgres_shdev"
        db_password = "Sonha@2024"

        try:
            connection = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            return connection

        except psycopg2.Error as e:
            raise UserError(f"Lỗi kết nối tới database: {str(e)}")

    def execute_query(self, query, params=None):
        connection = self.connect_to_external_db()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            # result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in cursor.fetchall()]
            connection.commit()
            return result
        except psycopg2.DatabaseError as e:
            raise UserError(f"Lỗi database: {e}")
        except Exception as e:
            raise UserError(f"Lỗi khác: {e}")
        finally:
            cursor.close()
            connection.close()

