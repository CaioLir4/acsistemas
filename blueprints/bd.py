import db_config
import mysql.connector

def criar_tabela_checklist():
    """Função para criar a tabela 'atendimentos' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checklist (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_usuario INT NOT NULL,
                        data_checklist DATETIME NOT NULL,
                        id_servico INT NOT NULL,
                        observacao TEXT,
                        FOREIGN KEY (id_usuario) REFERENCES usuarios(id),
                        FOREIGN KEY (id_servico) REFERENCES servicos(id)
                    );
                """)
                connection.commit()
                print("Tabela 'checklist' criada ou já existente.")
    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_escalas():
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS escalas (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        data DATE NOT NULL,
                        id_usuario INT NOT NULL,
                        tipo ENUM('domingo', 'feriado') NOT NULL,
                        observacao TEXT,
                        FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
                    );
                """)
                connection.commit()
                print("Tabela 'escalas' criada ou já existente.")
    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_atendimentos():
    """Função para criar a tabela 'atendimentos' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS atendimentos (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_cliente INT NOT NULL,
                        id_usuario INT NOT NULL,
                        data_atendimento DATETIME NOT NULL,
                        data_resolucao DATETIME,
                        id_servico INT NOT NULL,
                        observacao TEXT,
                        resolvido TINYINT(1) DEFAULT 0,  -- 0 para Não Resolvido, 1 para Resolvido
                        ativo TINYINT(1) DEFAULT 1,      -- 1 para Ativo, 0 para Inativo
                        FOREIGN KEY (id_cliente) REFERENCES clientes(id),
                        FOREIGN KEY (id_usuario) REFERENCES usuarios(id),
                        FOREIGN KEY (id_servico) REFERENCES servicos(id)
                    );
                """)
                connection.commit()
                print("Tabela 'atendimentos' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_clientes():
    """Função para criar a tabela 'clientes' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clientes (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nome VARCHAR(255) NOT NULL,
                        cpf_cnpj VARCHAR(20) NOT NULL,
                        versao VARCHAR(50),
                        versao_api VARCHAR(30),
                        drive_link TEXT,
                        data_ult_bckp VARCHAR(255),  -- Armazena a string da data
                        acesso_srv VARCHAR(255),      -- Armazena os acessos como string (números separados por vírgula)
                        acessos_trm VARCHAR(255),     -- Armazena os acessos como string (números separados por vírgula)
                        ativo TINYINT(1) DEFAULT 1,   -- 1 (ativo) ou 0 (inativo)
                        email VARCHAR(255),            -- Campo de email
                        ultima_consulta VARCHAR(255),
                        produto VARCHAR(255),
                        acompanhamento TINYINT(1) NOT NULL DEFAULT 0
                    );
                """)
                connection.commit()
                print("Tabela 'clientes' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_usuarios():
    """Função para criar a tabela 'usuarios' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        login VARCHAR(255) NOT NULL,
                        senha VARCHAR(255) NOT NULL
                    );
                """)
                connection.commit()
                print("Tabela 'usuarios' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_servicos():
    """Função para criar a tabela 'servicos' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS servicos (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nome VARCHAR(255) NOT NULL,
                        ativo TINYINT(1) DEFAULT 1,
                        tipo INT NOT NULL
                    );
                """)
                connection.commit()
                print("Tabela 'servicos' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_backups():
    """Função para criar a tabela 'backups' caso não exista."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS backups (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nome VARCHAR(255) NOT NULL,
                        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                connection.commit()
                print("Tabela 'backups' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_acompanhamento():
    """Cria a tabela 'acompanhamento' se não existir."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS acompanhamento (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_cliente INT NOT NULL,  -- Permite múltiplos acompanhamentos
                        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        treinamento_cadastros BOOLEAN DEFAULT FALSE,
                        treinamento_vendas BOOLEAN DEFAULT FALSE,
                        treinamento_estoque BOOLEAN DEFAULT FALSE,
                        treinamento_relatorios BOOLEAN DEFAULT FALSE,
                        financeiro BOOLEAN DEFAULT FALSE,
                        portal BOOLEAN DEFAULT FALSE,
                        backup_configurado BOOLEAN DEFAULT FALSE,
                        finalizado BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON DELETE CASCADE
                    );
                """)
                print("Tabela 'acompanhamento' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_acompanhamento_updates():
    """Cria a tabela 'acompanhamento_updates' se não existir."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS acompanhamento_updates (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_acompanhamento INT NOT NULL,
                        data_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        descricao TEXT,
                        pendencia BOOLEAN DEFAULT FALSE,
                        usuario INT NOT NULL,
                        FOREIGN KEY (id_acompanhamento) REFERENCES acompanhamento(id) ON DELETE CASCADE
                    );
                """)
                print("Tabela 'acompanhamento_updates' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_demanda():
    """Cria a tabela 'demanda' se não existir."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS demanda (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_usuario INT NOT NULL,  -- Usuário responsável pela demanda
                        titulo VARCHAR(255) NOT NULL,
                        descricao TEXT NOT NULL,
                        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status ENUM('Pendente', 'Em andamento', 'Concluída') DEFAULT 'Pendente',
                        prioridade ENUM('Baixa', 'Média', 'Alta') DEFAULT 'Média',
                        FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
                    );
                """)
                print("Tabela 'demanda' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_demanda_updates():
    """Cria a tabela 'demanda_updates' para acompanhar mudanças no status da demanda."""
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS demanda_updates (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        id_demanda INT NOT NULL,
                        data_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        descricao TEXT,
                        usuario INT NOT NULL,
                        FOREIGN KEY (id_demanda) REFERENCES demanda(id) ON DELETE CASCADE
                    );
                """)
                print("Tabela 'demanda_updates' criada ou já existente.")

    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")

    except Exception as e:
        print(f"Erro ao criar a tabela 'atendimentos': {e}")

def criar_tabela_versoes():
    try:
        connection = db_config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS versoes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    versao VARCHAR(10) NOT NULL,
                    pi VARCHAR(15) NOT NULL
                );
            """)
            connection.commit()
            print("Tabela 'versoes' criada ou já existente.")
    except mysql.connector.Error as err:
        print(f"Erro MySQL: {db_config.tratar_erro_mysql(err)}")
    except Exception as e:
        print(f"Erro ao criar a tabela 'versoes': {e}")