import mysql.connector
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from db_config import get_db_connection
from dotenv import load_dotenv
import os

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_JSON_PATH')

def autenticar_drive():
    """Autentica na API do Google Drive."""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

"""def verificar_ultimos_backups():
    service = autenticar_drive()  # Função que autentica no Google Drive
    pasta_nome = 'backup'
    backups = []

    try:
        page_token = None

        while True:
            # Busca os arquivos, usando o token da próxima página, se existir
            resultados = service.files().list(
                q=f"name contains '{pasta_nome}' and mimeType='application/vnd.google-apps.folder' and sharedWithMe",
                spaces='drive',
                fields="nextPageToken, files(id, name, owners(emailAddress))",
                pageSize=100,  # Máximo permitido por página
                pageToken=page_token
            ).execute()

            pastas = resultados.get('files', [])
            if not pastas and not page_token:
                print(f"Pasta '{pasta_nome}' não encontrada.")
                return backups

            a = 0

            for pasta in pastas:
                pasta_id = pasta['id']
                # Buscar arquivos dentro da pasta
                arquivos = service.files().list(
                    q=f"'{pasta_id}' in parents",
                    spaces='drive',
                    fields="files(name, modifiedTime)",
                    pageSize=100
                ).execute()

                arquivos = arquivos.get('files', [])
                if not arquivos:
                    continue

                arquivos.sort(key=lambda x: x['modifiedTime'], reverse=True)
                arquivo_mais_recente = arquivos[0]

                # Ajustando o horário para o fuso horário local
                modified_time = arquivo_mais_recente['modifiedTime']
                utc_time = datetime.strptime(modified_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                adjusted_time = utc_time - timedelta(hours=3)
                formatted_time = adjusted_time.strftime("%d/%m/%Y %H:%M")

                backup_info = {
                    'pasta_id': pasta_id,
                    'nome_pasta': pasta['name'],
                    'email_proprietarios': [owner['emailAddress'] for owner in pasta.get('owners', [])],
                    'arquivo_mais_recente': arquivo_mais_recente['name'],
                    'horario_backup': formatted_time
                }

                backups.append(backup_info)

                a += 1

                print(backup_info)
                print((5 * "="), a, (240 * "="))

            # Atualiza o token para buscar a próxima página
            page_token = resultados.get('nextPageToken', None)
            if not page_token:
                break

        return backups
    except Exception as e:
        print(f"Erro: {e}")
        return backups"""

def verificar_ultimos_backups():
    service = autenticar_drive()  # Função que autentica no Google Drive
    pasta_nome = 'backup'
    backups = []
    data_pi_jar = ""  # Para armazenar a data do arquivo PI.jar
    i = 1

    try:
        page_token = None

        while True:
            # Busca a pasta "backup"
            resultados = service.files().list(
                q=f"name = '{pasta_nome}' and mimeType='application/vnd.google-apps.folder' and sharedWithMe",
                spaces='drive',
                fields="nextPageToken, files(id, name, owners(emailAddress))",
                pageSize=100,
                pageToken=page_token
            ).execute()

            pastas = resultados.get('files', [])
            if not pastas:
                print(f"Pasta '{pasta_nome}' não encontrada.")
                return backups

            for pasta in pastas:
                pasta_id = pasta['id']

                # Buscar todos os arquivos dentro da pasta "backup"
                arquivos = service.files().list(
                    q=f"'{pasta_id}' in parents",
                    spaces='drive',
                    fields="files(name, modifiedTime)",
                    pageSize=100
                ).execute().get('files', [])

                if not arquivos:
                    continue

                # Buscar o arquivo mais recente (backup)
                arquivos.sort(key=lambda x: x['modifiedTime'], reverse=True)
                arquivo_mais_recente = arquivos[0]

                # Buscar a data do PI.jar
                for arquivo in arquivos:
                    if arquivo['name'] == "PI.jar":
                        modified_time_pi = arquivo['modifiedTime']
                        utc_time_pi = datetime.strptime(modified_time_pi, "%Y-%m-%dT%H:%M:%S.%fZ")
                        adjusted_time_pi = utc_time_pi - timedelta(hours=3)
                        data_pi_jar = adjusted_time_pi.strftime("%d/%m/%Y")
                        break  # Encontrou, pode sair do loop
                else:
                    data_pi_jar = ""

                # Ajustando o horário do backup para o fuso local
                modified_time = arquivo_mais_recente['modifiedTime']
                utc_time = datetime.strptime(modified_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                adjusted_time = utc_time - timedelta(hours=3)
                formatted_time = adjusted_time.strftime("%d/%m/%Y %H:%M")

                backup_info = {
                    'pasta_id': pasta_id,
                    'nome_pasta': pasta['name'],
                    'email_proprietarios': [owner['emailAddress'] for owner in pasta.get('owners', [])],
                    'arquivo_mais_recente': arquivo_mais_recente['name'],
                    'horario_backup': formatted_time,
                    'data_pi_jar': data_pi_jar  # Adiciona a data do PI.jar (se encontrado)
                }

                backups.append(backup_info)

                print(i,backup_info)
                i+=1

            page_token = resultados.get('nextPageToken', None)
            if not page_token:
                break

        return backups
    except Exception as e:
        print(f"Erro: {e}")
        return backups






def atualizar_backup():
    backups = verificar_ultimos_backups()

    if not backups:
        print("Nenhum backup para atualizar.")
        return

    try:
        # Conectar ao banco de dados
        connection = get_db_connection()
        cursor = connection.cursor()

        backups_nao_atualizados = []  # Lista para armazenar backups não atualizados

        for backup in backups:
            arquivo = str(backup['arquivo_mais_recente'])
            pasta_id = str(backup['pasta_id'])
            horario_backup = str(backup['horario_backup'])
            emails_proprietarios = ', '.join(backup['email_proprietarios'])
            data_pi_jar = str(backup['data_pi_jar'])
            
            # Formata a data/hora no formato brasileiro
            data_ultima_consulta = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # Atualiza a tabela cliente
            query = """
                UPDATE clientes
                SET ultimo_backup = %s, data_ult_bckp = %s, email = %s, ultima_consulta = %s, versao_api = %s
                WHERE drive_link LIKE CONCAT('%', %s, '%')
            """
            cursor.execute(query, (arquivo, horario_backup, emails_proprietarios, data_ultima_consulta, data_pi_jar, pasta_id))

            # Verifica se alguma linha foi afetada
            if cursor.rowcount == 0:
                backups_nao_atualizados.append(backup)

        # Confirma as alterações no banco de dados
        connection.commit()

        print("Dados atualizados com sucesso!")

        # Exibe os backups não atualizados
        if backups_nao_atualizados:
            print("\nBackups não atualizados no banco de dados:")
            for backup in backups_nao_atualizados:
                print(f"Backup não atualizado: {backup}")
        return backups_nao_atualizados

    except mysql.connector.Error as err:
        print(f"Erro ao conectar ao banco de dados: {err}")
