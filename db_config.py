import os
from dotenv import load_dotenv
import psycopg2

# Carregar variáveis do arquivo .env
load_dotenv()

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados PostgreSQL no Render."""
    try:
        connection = psycopg2.connect(os.getenv("DATABASE_URL"))
        return connection
    except psycopg2.Error as err:
        print(f"Erro PostgreSQL: {err}")
        return None

def tratar_erro_psycopg2(erro):
    """Trata os erros do psycopg2 e retorna uma mensagem amigável."""
    if isinstance(erro, psycopg2.ProgrammingError):
        return "Erro de programação no SQL. Verifique a sintaxe da consulta."
    elif isinstance(erro, psycopg2.IntegrityError):
        return "Erro de integridade dos dados. Possível violação de chave estrangeira ou dados inválidos."
    elif isinstance(erro, psycopg2.DatabaseError):
        return "Erro no banco de dados. Verifique a conexão e a estrutura da tabela."
    elif isinstance(erro, psycopg2.InterfaceError):
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


