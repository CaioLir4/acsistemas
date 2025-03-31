import os
from dotenv import load_dotenv
import mysql.connector

# Carregar variáveis do arquivo .env
load_dotenv()

def get_db_config():
    """Retorna a configuração do banco de dados."""
    return {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME')
    }

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    try:
        config = get_db_config()
        connection = mysql.connector.connect(**config)
        return connection
    except mysql.connector.Error as err:
        print(f"Erro MySQL: {err}")
        return None

def tratar_erro_mysql(erro):
    """Trata os erros do MySQL e retorna uma mensagem amigável."""
    if isinstance(erro, mysql.connector.ProgrammingError):
        return "Erro de programação no SQL. Verifique a sintaxe da consulta."
    elif isinstance(erro, mysql.connector.IntegrityError):
        return "Erro de integridade dos dados. Possível violação de chave estrangeira ou dados inválidos."
    elif isinstance(erro, mysql.connector.DatabaseError):
        return "Erro no banco de dados. Verifique a conexão e a estrutura da tabela."
    elif isinstance(erro, mysql.connector.InterfaceError):
        return "Erro na interface de conexão com o banco. O servidor pode estar inacessível."
    else:
        return f"Erro desconhecido: {erro}"

def testar_conec():

    connection = get_db_connection()

    if connection:
        print("✅ Conexão bem-sucedida!")
        connection.close()  # Fecha a conexão após o teste
    else:
        print("❌ Falha na conexão com o banco.")


