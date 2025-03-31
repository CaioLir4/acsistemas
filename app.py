from flask import Flask,jsonify,flash,g,request, render_template, make_response,redirect, url_for, session
from psycopg2.extras import RealDictCursor
from functools import wraps
import secrets
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime, timedelta,date
import api
from dotenv import load_dotenv
from db_config import get_db_connection,testar_conec
from blueprints.bd import *

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

load_dotenv()

backups_em_dia = 0
backups_atrasados = 0
backups_sem_registro = 0

#===============FUNÇÕES==================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def carregar_pendencias():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        # Contar quantas pendências existem
        cursor.execute("SELECT COUNT(*) as total_pendencias FROM atendimentos WHERE resolvido = 0")
        resultado = cursor.fetchone()

        # Pega o número total de pendências
        g.total_pendencias = resultado["total_pendencias"] if resultado else 0

    except Exception as e:
        g.total_pendencias = 0  # Caso ocorra erro, evita travar a página

#==================== ROTAS =======================
#================ AUTENTICAÇÃO ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha']

        try:
            connection = get_db_connection()  # Criando conexão dentro da função
            if connection is None:
                return "Erro ao conectar ao banco de dados: Conexão não disponível."

            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Verificar se o usuário e senha existem no banco de dados
                cursor.execute("SELECT * FROM usuarios WHERE login = %s AND senha = %s", (login, senha))
                usuario = cursor.fetchone()

                if usuario:
                    # Se encontrado, armazena o ID do usuário na sessão
                    session['user_id'] = usuario['id']
                    session['user_name'] = usuario['login']
                    return redirect(url_for('home'))
                else:
                    # Se não encontrado, exibe mensagem de erro
                    error = "Credenciais inválidas. Tente novamente."
                    return render_template('login.html', error=error)

        except psycopg2.Error as err:
            return f"Erro Postergree: {err}"
        except Exception as e:
            return f"Erro inesperado: {e}"

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Remove o usuário da sessão
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('login'))

#============== HOME  ==========================

@app.route('/')
@login_required
def home():


    user_id = session['user_id']  # Obtém o user_id da sessão

    try:
        connection = get_db_connection()
        if connection is None:
            return "Erro ao conectar ao banco de dados: Conexão não disponível."

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Consulta para obter o nome do usuário
            cursor.execute("SELECT login FROM usuarios WHERE id = %s", (user_id,))
            usuario = cursor.fetchone()  # Retorna um dicionário

            if usuario is None:
                return "Erro: Usuário não encontrado."

            user_nome = usuario['login']  # Obtém o nome corretamente

    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template('home.html', user_nome=user_nome)

#============== CLIENTE  ========================

@app.route('/clientes', methods=['GET'])
@login_required
def buscar_cliente():
    nome = request.args.get('nome', '')
    cnpj = request.args.get('cnpj', '').strip().replace('.', '').replace('/', '').replace('-', '')
    ativo = request.args.get('ativo', '1')
    page = int(request.args.get('page', 1))
    limit = 10
    offset = (page - 1) * limit

    query = "SELECT id, nome, cpf_cnpj, versao, data_ult_bckp, drive_link, acesso_srv FROM clientes WHERE 1=1"
    filters = []
    params = []

    if ativo == '2':
        pass
    else:
        filters.append("ativo = %s")
        params.append(int(ativo))

    if nome:
        filters.append("nome LIKE %s")
        params.append(f"%{nome}%")
    if cnpj:
        filters.append("cpf_cnpj LIKE %s")
        params.append(f"%{cnpj}%")

    if filters:
        query += " AND " + " AND ".join(filters)

    query += " ORDER BY nome LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            clientes = cursor.fetchall()

            count_query = "SELECT COUNT(*) as total FROM clientes WHERE 1=1"
            if filters:
                count_query += " AND " + " AND ".join(filters)

            count_params = params[:len(filters)]
            cursor.execute(count_query, count_params)
            total_clientes = cursor.fetchone()['total']

    except Exception as e:
        app.logger.error(f"Erro ao conectar ao banco de dados: {e}")
        return "Erro ao processar sua solicitação."

    total_paginas = (total_clientes + limit - 1) // limit

    # Se for acesso normal, retorna a página completa
    return render_template('clientes.html', clientes=clientes, page=page, total_paginas=total_paginas)

@app.route('/clientes/novo', methods=['GET', 'POST'])
@login_required
def cadastrar_cliente():
    if request.method == 'POST':
        # Captura dos dados do formulário e remove espaços extras
        nome = request.form.get('nome', '').strip()
        cpf_cnpj = request.form.get('cpf_cnpj', "").strip().replace('.', '').replace('/', '').replace('-', '')  # Normaliza CNPJ
        versao = request.form.get('versao', '').strip()
        email = request.form.get('email', '').strip()
        drive_link = request.form.get('drive_link', '').strip()
        acesso_srv = request.form.get('acesso_srv', '').strip()
        acessos_trm = request.form.get('acessos_trm', '').strip()

        try:
            # Conectando ao banco de dados
            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Verifica se o CNPJ já existe no banco
                    cursor.execute("SELECT id FROM clientes WHERE cpf_cnpj = %s", (cpf_cnpj,))
                    cliente_existente = cursor.fetchone()

                    if cliente_existente:
                        flash('Erro: CNPJ já cadastrado!', 'danger')
                        return redirect(url_for('cadastrar_cliente'))

                    # Insere o novo cliente
                    cursor.execute("""
                        INSERT INTO clientes 
                        (nome, cpf_cnpj, versao, drive_link, acesso_srv, acessos_trm, email, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (nome, cpf_cnpj, versao, drive_link, acesso_srv, acessos_trm, email, 1))

                    novo_id = cursor.lastrowid  # Obtém o ID do cliente recém-criado
                    connection.commit()

                    flash('Cliente cadastrado com sucesso!', 'success')
                    return redirect(url_for('editar_cliente', id=novo_id))

        except Exception as e:
            flash(f'Erro ao cadastrar cliente: {e}', 'danger')

    return render_template('cliente_form.html', cliente=None)

@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    try:
        # Abrir conexão com o banco de dados
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Buscar cliente para edição
                cursor.execute("SELECT c.*, v.versao FROM clientes c "
                               "inner join versoes v on c.versao_api = v.pi WHERE c.id = %s", (id,))
                cliente = cursor.fetchone()
                if not cliente:
                    flash('Cliente não encontrado.', 'warning')
                    return redirect(url_for('buscar_cliente'))
    except Exception as e:
        print(f"Erro ao acessar o banco de dados: {e}")
        flash('Erro ao acessar o banco de dados.', 'danger')
        return redirect(url_for('buscar_cliente'))

    if request.method == 'POST':
        try:
            # Captura dos dados do formulário
            nome = request.form['nome']
            cpf_cnpj = request.form['cpf_cnpj']
            versao = request.form['versao']
            email = request.form['email']
            ultimo_backup = request.form.get('ultimo_backup')  # Default para None se não existir
            drive_link = request.form.get('drive_link')  # Default para None se não existir
            acesso_srv = request.form.get('acesso_srv')  # Default para None se não existir
            acessos_trm = request.form.get('acessos_trm')  # Default para None se não existir
            data_ult_bckp = request.form.get('data_ult_bckp')  # Default para None se não existir
            ativo = request.form.get('ativo', '1')  # Valor padrão é '1' (Sim)
            produto = request.form.get('produto')

            # Atualizar cliente
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE clientes
                        SET nome = %s, cpf_cnpj = %s, versao = %s, ultimo_backup = %s, 
                            drive_link = %s, acesso_srv = %s, acessos_trm = %s, data_ult_bckp = %s, 
                            email = %s, ativo = %s, produto = %s
                        WHERE id = %s
                    """, (nome, cpf_cnpj, versao, ultimo_backup, drive_link, acesso_srv, acessos_trm,
                          data_ult_bckp, email, ativo,produto, id))
                    connection.commit()

            # Exibe mensagem de sucesso
            flash('Cliente atualizado com sucesso!', 'success')
            return redirect(url_for('editar_cliente', id=id))

        except Exception as e:
            print(f"Erro ao atualizar cliente: {e}")
            # Exibe mensagem de erro
            flash('Erro ao atualizar cliente.', 'danger')

    # Renderizar o formulário com os dados do cliente existentes
    return render_template('cliente_form.html', cliente=cliente)

@app.route('/cliente/<int:cliente_id>/acessos')
@login_required
def acessos_cliente(cliente_id):
    try:
        # Conexão com o banco

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Obter os dados do cliente
            cursor.execute("SELECT nome, acesso_srv, acessos_trm FROM clientes WHERE id = %s", (cliente_id,))
            cliente = cursor.fetchone()
            if not cliente:
                return "Cliente não encontrado.", 404

            # Processar os acessos
            acessos = []
            if cliente['acesso_srv']:
                acessos.append({"nome": "Servidor", "link": f"anydesk:{cliente['acesso_srv']}", "numero": f"{cliente['acesso_srv']}"})

            if cliente['acessos_trm']:
                terminais = cliente['acessos_trm'].split(",")
                for i, terminal in enumerate(terminais, start=1):
                    acessos.append({"nome": f"Terminal {i}", "link": f"anydesk:{terminal.strip()}", "numero": f"{terminal.strip()}" })

            return render_template('acessos.html', cliente=cliente, acessos=acessos)

    except psycopg2.Error as err:
        return f"Erro ao acessar o banco de dados: {err}", 500

#============== ATENDIMENTO  ======================

@app.route('/atendimentos', methods=['GET', 'POST'])
@login_required
def atendimentos():


    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        id_usuario = request.form['id_usuario']
        data_inicio = request.form['data_inicio']
        data_fim = request.form['data_fim']
        resolvido = request.form['resolvido']
        id_servico = request.form['id_servico']
        observacao = request.form['observacao']


        # Conectando ao banco de dados
        try:

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                if resolvido == '0':
                    # Inserir o atendimento no banco de dados
                    cursor.execute("""
                        INSERT INTO atendimentos (id_cliente, id_usuario, data_atendimento, id_servico, observacao, resolvido)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (id_cliente, id_usuario, data_inicio, id_servico, observacao, resolvido))
                    connection.commit()
                    return redirect('/atendimentos')

                else:
                    # Inserir o atendimento no banco de dados
                    cursor.execute("""
                                        INSERT INTO atendimentos (id_cliente, id_usuario, data_atendimento, id_servico, observacao, resolvido, data_resolucao)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (id_cliente, id_usuario, data_inicio, id_servico, observacao, resolvido, data_fim))
                    connection.commit()
                    return redirect('/atendimentos')

        except Exception as e:
            return f"Erro ao registrar o atendimento: {e}"

    # Caso GET: Exibir o formulário
    try:

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Obter todos os clientes
            cursor.execute("SELECT id, nome, cpf_cnpj FROM clientes where ativo = 1 ORDER BY nome")
            clientes = cursor.fetchall()

            # Obter todos os usuários
            cursor.execute("SELECT id, login FROM usuarios")
            usuarios = cursor.fetchall()

            # Obter todos os serviços disponíveis
            cursor.execute("SELECT id, nome FROM servicos order by nome")
            servicos = cursor.fetchall()

    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template('atendimentos.html', clientes=clientes, usuarios=usuarios, servicos=servicos)

@app.route('/historico', methods=['GET', 'POST'])
@login_required
def historico_atendimentos():


    # Filtros
    cliente_id = request.args.get('id_cliente')  # ID do cliente para filtro
    data_inicio = request.args.get('data_inicio')  # Data de início para filtro
    data_fim = request.args.get('data_fim')  # Data de fim para filtro
    status = request.args.get('status')  # Status de ativo ou inativo
    situacao = request.args.get('situacao')
    id_usuario = request.args.get('id_usuario')  # ID do usuário para filtro
    id_servico = request.args.get('id_servico')  # ID do serviço para filtro

    # Monta a query com filtros
    query = """
        SELECT a.*, c.nome AS cliente_nome, u.login AS usuario_nome, s.nome AS servico_nome 
        FROM atendimentos a
        INNER JOIN clientes c ON a.id_cliente = c.id 
        INNER JOIN usuarios u ON a.id_usuario = u.id 
        INNER JOIN servicos s ON a.id_servico = s.id
        WHERE a.ativo = 1
    """  # Filtro padrão para ativos

    filters = []
    params = []

    # Adiciona filtros
    if status:
        query += " AND a.ativo = %s "
        filters.append(status)

    if situacao:
        query += " AND a.resolvido = %s "
        filters.append(situacao)

    if cliente_id:
        query += " AND a.id_cliente = %s "
        filters.append(cliente_id)

    if id_usuario:
        query += " AND u.id = %s "
        filters.append(id_usuario)

    if id_servico:
        query += " AND a.id_servico = %s "
        filters.append(id_servico)

    if data_inicio and data_fim:
        query += " AND DATE(a.data_atendimento) BETWEEN %s AND %s "
        filters.append(data_inicio)
        filters.append(data_fim)

    query += " ORDER BY a.data_atendimento"

    try:
        # Conexão com o banco de dados

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Consulta para resolver pendentes e resolvidos
            cursor.execute(
                "SELECT "
                "SUM(CASE WHEN resolvido = 0 THEN 1 ELSE 0 END) AS total_pendentes, "
                "SUM(CASE WHEN resolvido = 1 THEN 1 ELSE 0 END) AS total_resolvidos "
                "FROM atendimentos;"
            )
            result = cursor.fetchone()
            at_pendentes = result["total_pendentes"]
            at_resolvidos = result["total_resolvidos"]

            # Executa a consulta com os filtros
            cursor.execute(query, tuple(filters))
            atendimentos = cursor.fetchall()

            # Calcular total de atendimentos ativos
            count_query = """
                SELECT COUNT(*) FROM atendimentos a
                WHERE a.ativo = 1
            """  # Filtro padrão para ativos

            count_filters = []

            if status:
                count_query += " AND a.ativo = %s"
                count_filters.append(status)

            if cliente_id:
                count_query += " AND a.id_cliente = %s"
                count_filters.append(cliente_id)

            if id_usuario:
                count_query += " AND a.id_usuario = %s"
                count_filters.append(id_usuario)

            if id_servico:
                count_query += " AND a.id_servico = %s"
                count_filters.append(id_servico)

            if data_inicio and data_fim:
                count_query += " AND DATE(a.data_atendimento) BETWEEN %s AND %s"
                count_filters.append(data_inicio)
                count_filters.append(data_fim)

            cursor.execute(count_query, tuple(count_filters))
            total_atendimentos_ativos = cursor.fetchone()['COUNT(*)']

            # Consulta todos os clientes para preencher o filtro
            cursor.execute("SELECT id, nome FROM clientes ORDER BY nome")
            clientes = cursor.fetchall()

            # Consulta todos os usuários para preencher o filtro de usuário
            cursor.execute("SELECT id, login FROM usuarios")
            usuarios = cursor.fetchall()

            # Consulta todos os serviços para preencher o filtro de serviço
            cursor.execute("SELECT id, nome FROM servicos ORDER BY nome")
            servicos = cursor.fetchall()

    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template('historico_atendimentos.html',
                           atendimentos=atendimentos,
                           clientes=clientes,
                           usuarios=usuarios,
                           servicos=servicos,
                           total_atendimentos_ativos=total_atendimentos_ativos,
                           at_resolvidos=at_resolvidos,
                           at_pendentes=at_pendentes)

@app.route('/atendimento/<int:id_atendimento>/atualizar_situacao', methods=['POST'])
@login_required
def atualizar_situacao(id_atendimento):
    """
    Atualiza a situação de um atendimento (Resolvido ou Pendente).
    """
    try:
        # Obtém a nova situação enviada pelo formulário
        nova_situacao = int(request.form.get('situacao'))

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                UPDATE atendimentos
                SET situacao = %s
                WHERE id = %s
            """
            cursor.execute(query, (nova_situacao, id_atendimento))
            psycopg2.connection.commit()

            # Exibe mensagem de sucesso
            flash('Situação do atendimento atualizada com sucesso!', 'success')

    except Exception as e:
        # Exibe mensagem de erro caso algo dê errado
        flash(f'Erro ao atualizar situação: {str(e)}', 'danger')

    # Redireciona de volta para a página de histórico de atendimentos
    return redirect(url_for('historico_atendimentos'))

@app.route('/inutilizar_atendimento/<int:id_atendimento>', methods=['POST'])
@login_required
def inutilizar_atendimento(id_atendimento):

    try:
        # Conexão com o banco de dados

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Atualiza o atendimento para inativo
            cursor.execute("UPDATE atendimentos SET ativo = 0 WHERE id = %s", (id_atendimento,))
            connection.commit()

            # Redireciona para a página de histórico
            return redirect('/historico')

    except Exception as e:
        return f"Erro ao atualizar o atendimento: {e}"

#================== DASHBOARD ========================

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Obtendo o user_id da sessão

    global backups_em_dia, backups_atrasados, backups_sem_registro

    try:
        con = get_db_connection()
        cursor = con.cursor()

        # Consulta para resolver pendentes e resolvidos por tipo
        cursor.execute(
            "SELECT "
            "c.produto, "
            "SUM(CASE WHEN a.resolvido = 0 THEN 1 ELSE 0 END) AS total_pendentes, "
            "SUM(CASE WHEN a.resolvido = 1 THEN 1 ELSE 0 END) AS total_resolvidos "
            "FROM atendimentos a "
            "INNER JOIN clientes c ON c.id = a.id_cliente "
            "WHERE a.ativo = 1 "
            "GROUP BY c.produto;"
        )

        result = cursor.fetchall()

        # Criar dicionário para armazenar os valores por tipo
        dados_atendimentos = {
            "LC": {"pendentes": 0, "resolvidos": 0},
            "CPLUG": {"pendentes": 0, "resolvidos": 0}
        }
        for tipo, pendentes, resolvidos in result:
            if tipo in dados_atendimentos:
                dados_atendimentos[tipo]["pendentes"] = pendentes
                dados_atendimentos[tipo]["resolvidos"] = resolvidos

        # Consulta para obter o nome do usuário
        cursor.execute("SELECT login FROM usuarios WHERE id = %s", (user_id,))
        user_nome = cursor.fetchone()[0]  # Obtém o nome do usuário

        # Receber as datas do filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')

        # Montar a consulta para contar os atendimentos ativos com filtro de data
        query_atendimentos_ativos_LC = """
            SELECT COUNT(*)
            FROM atendimentos a
            INNER JOIN clientes c ON c.id = a.id_cliente
            WHERE a.ativo = 1 AND c.produto = 'LC';
        """

        query_atendimentos_ativos_CPLUG = """
                    SELECT COUNT(*)
                    FROM atendimentos a
                    INNER JOIN clientes c ON c.id = a.id_cliente
                    WHERE a.ativo = 1 AND c.produto = 'CPLUG';
                """

        # Adicionar o filtro de data, se fornecido
        if data_inicio:
            query_atendimentos_ativos_LC += f" AND DATE(data_atendimento) >= '{data_inicio}'"
        if data_fim:
            query_atendimentos_ativos_LC += f" AND DATE(data_atendimento) <= '{data_fim}'"

        # Adicionar o filtro de data, se fornecido
        if data_inicio:
            query_atendimentos_ativos_CPLUG += f" AND DATE(data_atendimento) >= '{data_inicio}'"
        if data_fim:
            query_atendimentos_ativos_CPLUG += f" AND DATE(data_atendimento) <= '{data_fim}'"

        # Executar a consulta para total de atendimentos ativos
        cursor.execute(query_atendimentos_ativos_LC)
        total_atendimentos_ativos_LC = cursor.fetchone()[0]

        # Executar a consulta para total de atendimentos ativos
        cursor.execute(query_atendimentos_ativos_CPLUG)
        total_atendimentos_ativos_CPLUG = cursor.fetchone()[0]


        # Consulta para contar os clientes
        cursor.execute("SELECT COUNT(*) FROM clientes where ativo = 1 and produto = 'LC';")
        total_clientes_LC = cursor.fetchone()[0]

        # Consulta para contar os clientes
        cursor.execute("SELECT COUNT(*) FROM clientes where ativo = 1 and produto = 'CPLUG';")
        total_clientes_CPLUG = cursor.fetchone()[0]

        # Consulta para contar os clientes com backup configurado
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE drive_link IS NOT NULL AND drive_link != ' '")
        total_clientes_com_backup = cursor.fetchone()[0]

        # Montar a consulta SQL para o gráfico de pizza com filtro de data
        query_pie_chart = """
            SELECT u.login, COUNT(*)
            FROM atendimentos a
            INNER JOIN usuarios u ON a.id_usuario = u.id
            WHERE a.ativo = 1
        """

        # Adicionar o filtro de data, se fornecido
        if data_inicio:
            query_pie_chart += f" AND DATE(a.data_atendimento) >= '{data_inicio}'"
        if data_fim:
            query_pie_chart += f" AND DATE(a.data_atendimento) <= '{data_fim}'"

        query_pie_chart += " GROUP BY u.login"

        # Executar a consulta para o gráfico de pizza
        cursor.execute(query_pie_chart)
        pie_chart_data = cursor.fetchall()

        # Processando os dados para o gráfico de pizza
        categorias = [row[0] for row in pie_chart_data]
        valores = [row[1] for row in pie_chart_data]

        # Criando o gráfico de pizza com Plotly
        fig_pie = go.Figure(data=[go.Pie(labels=categorias, values=valores)])
        fig_pie.update_traces(textinfo='percent+label', pull=[0.1, 0.1, 0])  # Efeito de destaque no gráfico de pizza

        # Ajuste no tamanho do gráfico de pizza
        fig_pie.update_layout(
            width=600,  # Largura do gráfico em pixels
            height=260,  # Altura do gráfico em pixels
            margin=dict(l=10, r=10, t=10, b=10)  # Margens ao redor do gráfico
        )

        pie_chart_html = fig_pie.to_html(full_html=False)

        # Montar a consulta SQL para o gráfico de barras (atendimentos por tipo de serviço)
        query_bar_chart = """
            SELECT a.id_servico, COUNT(*), s.nome
            FROM atendimentos a
            INNER JOIN servicos s ON a.id_servico = s.id
            WHERE a.ativo = 1
        """

        # Adicionar o filtro de data, se fornecido
        if data_inicio:
            query_bar_chart += f" AND DATE(a.data_atendimento) >= '{data_inicio}'"
        if data_fim:
            query_bar_chart += f" AND DATE(a.data_atendimento) <= '{data_fim}'"

        query_bar_chart += " GROUP BY a.id_servico, s.nome ORDER BY COUNT(*) DESC"

        # Executar a consulta para o gráfico de barras
        cursor.execute(query_bar_chart)
        bar_chart_data = cursor.fetchall()

        # Processando os dados para o gráfico de barras
        tipos_servico = [row[2] for row in bar_chart_data]  # Nome do serviço
        atendimentos_por_tipo = [row[1] for row in bar_chart_data]  # Contagem de atendimentos

        # Criando o gráfico de barras com Plotly (estilo similar ao gráfico de pizza)
        fig_bar = go.Figure(data=[go.Bar(x=tipos_servico, y=atendimentos_por_tipo, text=atendimentos_por_tipo, textposition='auto', marker=dict(color='rgb(55, 83, 109)'))])
        fig_bar.update_layout(
            plot_bgcolor='rgb(242, 242, 242)',
            paper_bgcolor='rgb(242, 242, 242)',
            font=dict(size=14),
            showlegend=False
        )
        bar_chart_html = fig_bar.to_html(full_html=False)
    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template(
        'dashboard.html',
        total_atendimentos_ativos_LC=total_atendimentos_ativos_LC,
        total_atendimentos_ativos_CPLUG=total_atendimentos_ativos_CPLUG,
        total_clientes_LC = total_clientes_LC,
        total_clientes_CPLUG =total_clientes_CPLUG,
        total_clientes_com_backup=total_clientes_com_backup,
        pie_chart_html=pie_chart_html,
        bar_chart_html=bar_chart_html,
        data_inicio=data_inicio,
        data_fim=data_fim,
        user_nome=user_nome,
        backups_em_dia=backups_em_dia,
        backups_atrasados=backups_atrasados,
        backups_sem_registro=backups_sem_registro,
        at_pendentes_lc=dados_atendimentos["LC"]["pendentes"],
        at_resolvidos_lc=dados_atendimentos["LC"]["resolvidos"],
        at_pendentes_cplug=dados_atendimentos["CPLUG"]["pendentes"],
        at_resolvidos_cplug=dados_atendimentos["CPLUG"]["resolvidos"]
    )

@app.route('/gerar-pdf-backup', methods=['GET'])
def gerar_pdf_backup():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        con = get_db_connection()
        cursor = con.cursor()

        # Verifica se o parâmetro "status" foi passado na URL (ex: "ok" ou "gerar")
        status = request.args.get('status')

        if status == 'ok':  # Clientes com "referencias" preenchido
            cursor.execute("SELECT id, nome, cpf_cnpj FROM clientes WHERE drive_link IS NOT NULL AND drive_link != '' AND ativo = 1 ORDER BY id")
            clientes = cursor.fetchall()
            titulo_pdf = "Clientes com Backup Configurado"
        else:  # Clientes sem "referencias"
            cursor.execute("SELECT id, nome, cpf_cnpj FROM clientes WHERE (drive_link IS NULL OR drive_link = '') AND ativo = 1 ORDER BY id")
            clientes = cursor.fetchall()
            titulo_pdf = "Clientes sem Backup Configurado"

        # Gerando o PDF com FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=8)
        pdf.cell(200, 10, txt=titulo_pdf, ln=True, align="C")
        pdf.ln(10)

        # Adicionando os clientes ao PDF
        for cliente in clientes:
            pdf.cell(0, 8, txt=f"{cliente[0]} - {cliente[1]} : {cliente[2]} ", ln=True)

        # Retorna o PDF como resposta
        response = make_response(pdf.output(dest='S').encode('latin1'))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=clientes_backup.pdf'
        return response

    except Exception as e:
        return f"Erro ao gerar o PDF: {e}"

@app.route('/gerar-pdf-clientes', methods=['GET'])
def gerar_pdf_clientes():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        con = get_db_connection()
        cursor = con.cursor()

        # Consulta para contar o total de clientes ativos
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE ativo = 1")
        total_clientes = cursor.fetchone()[0]

        # Consulta para buscar os dados dos clientes ativos
        cursor.execute("SELECT id, nome, cpf_cnpj, versao FROM clientes WHERE ativo = 1")
        clientes = cursor.fetchall()

        # Consulta para contar os clientes por versão
        cursor.execute("""
            SELECT versao, COUNT(*) 
            FROM clientes 
            WHERE ativo = 1
            GROUP BY versao
        """)
        versoes = cursor.fetchall()

        # Gerando o PDF com FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Relatório de Total de Clientes", ln=True, align="C")
        pdf.ln(10)

        # Adicionando o total de clientes ao PDF
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, txt=f"Total de clientes cadastrados e ativos: {total_clientes}", ln=True)
        pdf.ln(5)

        # Adicionando a contagem por versão ao PDF
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(80, 8, txt="Versão", border=1, align="C")
        pdf.cell(40, 8, txt="Quantidade", border=1, align="C")
        pdf.ln()

        # Adicionando as versões e quantidades ao PDF
        pdf.set_font("Arial", size=10)
        for versao in versoes:
            # Convertendo a tupla para lista
            versao_list = list(versao)
            if versao_list[0] == '':
                versao_list[0] = '?'  # Agora podemos modificar a versão
            pdf.cell(80, 8, txt=versao_list[0], border=1, align="C")
            pdf.cell(40, 8, txt=str(versao_list[1]), border=1, align="C")
            pdf.ln()

        # Adicionando os dados dos clientes ao PDF
        pdf.set_font("Arial", style="B", size=10)
        pdf.ln(5)
        pdf.cell(20, 8, txt="ID", border=1, align="C")
        pdf.cell(100, 8, txt="Nome", border=1, align="C")
        pdf.cell(40, 8, txt="CPF/CNPJ", border=1, align="C")
        pdf.cell(30, 8, txt="Versao", border=1, align="C")
        pdf.ln()

        pdf.set_font("Arial", size=10)
        for cliente in clientes:
            pdf.cell(20, 8, txt=str(cliente[0]), border=1, align="C")  # ID
            pdf.cell(100, 8, txt=cliente[1], border=1, align="L")      # Nome
            pdf.cell(40, 8, txt=cliente[2], border=1, align="C")        # CPF/CNPJ
            pdf.cell(30, 8, txt=cliente[3], border=1, align="C")        # Referência
            pdf.ln()

        # Retorna o PDF como resposta
        response = make_response(pdf.output(dest='S').encode('latin1'))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=clientes_ativos.pdf'

        return response

    except Exception as e:
        return f"Erro ao gerar o PDF: {e}"

@app.route("/gerar-pdf", methods=['GET','POST'])
def gerar_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Obtendo o user_id da sessão
    tipo = request.args.get('tipo')

    try:
        con = get_db_connection()
        cursor = con.cursor()

        # Consulta para obter o nome do usuário
        cursor.execute("SELECT login FROM usuarios WHERE id = %s", (user_id,))
        user_nome = cursor.fetchone()
        if not user_nome:
            return "Usuário não encontrado."
        user_nome = user_nome[0]

        if tipo == 'diario':
            data_inicio = date.today()
            data_fim = date.today()

        if tipo == 'geral':
            data_inicio = None
            data_fim = None

        if tipo == 'personalizado':
            data_inicio = request.form.get('data_inicio')
            data_fim = request.form.get('data_fim')

        # Consulta: total de atendimentos ativos
        query_atendimentos_ativos = """
            SELECT COUNT(*) 
            FROM atendimentos 
            WHERE ativo = 1
        """
        filters = []
        if data_inicio and data_fim:
            query_atendimentos_ativos += " AND DATE(data_atendimento) BETWEEN %s AND %s"
            filters.extend([data_inicio, data_fim])

        cursor.execute(query_atendimentos_ativos, tuple(filters))
        total_atendimentos_ativos = cursor.fetchone()[0]

        # Consulta: total de clientes ativos
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE ativo = 1")
        total_clientes = cursor.fetchone()[0]

        # Consulta: total de clientes com backup configurado
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE drive_link IS NOT NULL AND drive_link != ''")
        total_clientes_com_backup = cursor.fetchone()[0]

        # Consulta: gráfico de pizza (atendimentos por usuário)
        query_pie_chart = """
            SELECT u.login, COUNT(*)
            FROM atendimentos a
            INNER JOIN usuarios u ON a.id_usuario = u.id
            WHERE a.ativo = 1
        """
        if data_inicio and data_fim:
            query_pie_chart += " AND DATE(a.data_atendimento) BETWEEN %s AND %s"
        query_pie_chart += " GROUP BY u.login"

        cursor.execute(query_pie_chart, tuple(filters))
        pie_chart_data = cursor.fetchall()

        # Preparar gráfico de pizza
        categorias = [row[0] for row in pie_chart_data]
        valores = [row[1] for row in pie_chart_data]
        fig_pie = go.Figure(data=[go.Pie(labels=categorias, values=valores)])
        fig_pie.update_traces(textinfo='percent+label', pull=[0.1, 0.1, 0])
        pie_chart_html = fig_pie.to_html(full_html=False)

        fig_pie.update_layout(
            width=100,  # Largura do gráfico em pixels
            height=400,  # Altura do gráfico em pixels
        )
        # Consulta: gráfico de barras (atendimentos por tipo de serviço)
        query_bar_chart = """
            SELECT s.nome, COUNT(*)
            FROM atendimentos a
            INNER JOIN servicos s ON a.id_servico = s.id
            WHERE a.ativo = 1
        """
        if data_inicio and data_fim:
            query_bar_chart += " AND DATE(a.data_atendimento) BETWEEN %s AND %s"
        query_bar_chart += " GROUP BY s.nome ORDER BY COUNT(*) DESC"

        cursor.execute(query_bar_chart, tuple(filters))
        bar_chart_data = cursor.fetchall()

        # Preparar gráfico de barras
        tipos_servico = [row[0] for row in bar_chart_data]
        atendimentos_por_tipo = [row[1] for row in bar_chart_data]
        fig_bar = go.Figure(data=[
            go.Bar(x=tipos_servico, y=atendimentos_por_tipo, text=atendimentos_por_tipo, textposition='auto')
        ])
        fig_bar.update_layout(
            plot_bgcolor='rgb(242, 242, 242)',
            paper_bgcolor='rgb(242, 242, 242)',
            font=dict(size=14),
            showlegend=False
        )
        bar_chart_html = fig_bar.to_html(full_html=False)

        # Consulta: atendimentos detalhados
        query_atendimentos = """
            SELECT a.*, c.nome AS cliente_nome, u.login AS usuario_nome, s.nome AS servico_nome 
            FROM atendimentos a
            INNER JOIN clientes c ON a.id_cliente = c.id 
            INNER JOIN usuarios u ON a.id_usuario = u.id 
            INNER JOIN servicos s ON a.id_servico = s.id
            WHERE a.ativo = 1
        """
        if data_inicio and data_fim:
            query_atendimentos += " AND DATE(a.data_atendimento) BETWEEN %s AND %s"
        query_atendimentos += " ORDER BY a.data_atendimento"

        cursor.execute(query_atendimentos, tuple(filters))
        atendimentos = cursor.fetchall()

        # Formatar atendimentos
        atendimentos_formatados = []
        for atendimento in atendimentos:
            data_formatada = datetime.strptime(str(atendimento[3]), '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M:%S')
            atendimento_formatado = list(atendimento)
            atendimento_formatado[3] = data_formatada
            atendimentos_formatados.append(atendimento_formatado)

        # Consulta: checklists
        query_checklists = """
                SELECT c.data_checklist, s.nome, u.login, c.observacao
                FROM checklist c
                JOIN servicos s ON c.id_servico = s.id
                JOIN usuarios u ON c.id_usuario = u.id
            """
        if data_inicio and data_fim:
            query_checklists += "WHERE DATE(c.data_checklist) BETWEEN %s AND %s"
        query_checklists += " ORDER BY u.login"

        cursor.execute(query_checklists, tuple(filters))
        checklists = cursor.fetchall()

        checklists_formatados = []
        for checklist in checklists:
            data_formatada = datetime.strptime(str(checklist[0]), '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M:%S')
            checklists_formatado = list(checklist)
            checklists_formatado[0] = data_formatada
            checklists_formatados.append(checklists_formatado)
        print(checklists_formatados)

    except psycopg2.Error as e:
        return f"Erro Postergree: {e}"
    except Exception as e:
        return f"Erro geral: {str(e)}"

    # Preparar dados para o contexto do template
    context = {
        'total_atendimentos_ativos': total_atendimentos_ativos,
        'total_clientes': total_clientes,
        'total_clientes_com_backup': total_clientes_com_backup,
        'pie_chart_html': pie_chart_html,
        'bar_chart_html': bar_chart_html,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'user_nome': user_nome,
        'atendimentos': atendimentos_formatados,
        'data': date.today().strftime('%d/%m/%Y'),
        'tipo': tipo
    }
    print(context['atendimentos'])

    # Adicionar checklists somente se o tipo for 'diario'
    if (tipo == 'diario') or (tipo == 'personalizado') :
        context['checklists'] = checklists_formatados

    # Renderizar o template com o contexto
    return render_template('relatorio.html', **context)

#================== ESCALAS ========================

@app.route('/escalas', methods=['GET', 'POST'])
@login_required
def registrar_escala():


    if request.method == 'POST':
        data = request.form.get('data')
        id_usuario = request.form.get('id_usuario')
        tipo = request.form.get('tipo')  # domingo ou feriado
        observacao = request.form.get('observacao')

        if not data or not id_usuario or not tipo:
            return "Data, funcionário e tipo são obrigatórios.", 400

        try:
            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                # Insere a nova escala
                cursor.execute("""
                    INSERT INTO escalas (data, id_usuario, tipo, observacao)
                    VALUES (%s, %s, %s, %s)
                """, (data, id_usuario, tipo, observacao))
                connection.commit()

        except Exception as e:
            return f"Erro ao salvar no banco de dados: {e}"

        return redirect(url_for('registrar_escala'))

    # Consulta os usuários para o formulário
    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Consulta os usuários disponíveis
            cursor.execute("SELECT id, login FROM usuarios")
            usuarios = cursor.fetchall()

            # Consulta as escalas registradas
            cursor.execute("""
                SELECT e.*, u.login AS usuario_nome 
                FROM escalas e 
                INNER JOIN usuarios u ON e.id_usuario = u.id
                ORDER BY e.data DESC
            """)
            escalas = cursor.fetchall()

    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template('escalas.html', usuarios=usuarios, escalas=escalas)

#================== CHECKLIST ======================
@app.route('/checklist', methods=['GET', 'POST'])
@login_required
def checklist():


    if request.method == 'POST':
        id_usuario = request.form['id_usuario']
        data = request.form['data']
        hora = request.form['hora']
        id_servico = request.form['id_servico']
        observacao = request.form['observacao']

        # Combine data e hora
        data_hora = f"{data} {hora}"

        # Conectando ao banco de dados
        try:

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                # Inserir o atendimento no banco de dados
                cursor.execute("""
                    INSERT INTO checklist (id_usuario, data_checklist, id_servico, observacao)
                    VALUES (%s, %s, %s, %s)
                """, (id_usuario, data_hora, id_servico, observacao))
                connection.commit()
                return redirect('/checklist')  # Redireciona de volta para a página de atendimentos

        except Exception as e:
            return f"Erro ao registrar o checklist: {e}"

    # Caso GET: Exibir o formulário
    try:
        # Conectar ao banco para obter os clientes e usuários

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Obter todos os usuários
            cursor.execute("SELECT id, login FROM usuarios")
            usuarios = cursor.fetchall()

            # Obter todos os serviços disponíveis
            cursor.execute("SELECT id, nome FROM servicos where tipo = 2 order by nome ")
            servicos = cursor.fetchall()

    except Exception as e:
        return f"Erro ao conectar ao banco de dados: {e}"

    return render_template('checklist.html', usuarios=usuarios, servicos=servicos)

#================== SERVICOS =======================

@app.route('/servicos/novo', methods=['GET', 'POST'])
@login_required
def cadastrar_servico():
    if request.method == 'POST':
        # Captura os dados do formulário
        nome = request.form.get('nome')
        tipo = request.form.get('tipo')

        # Aguardando confirmação do tipo de serviço no modal
        if tipo not in ['1', '2']:  # Se o tipo não for 1 ou 2, retornar erro
            flash('Selecione um tipo válido para o serviço!', 'danger')
            return render_template('servico_form.html', servico=None)

        try:
            # Conexão com o banco de dados

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                # Inserção no banco de dados
                cursor.execute("""
                    INSERT INTO servicos (nome, tipo, ativo)
                    VALUES (%s, %s, %s)
                """, (nome, tipo, 1))
                connection.commit()

                # Exibe mensagem de sucesso
                flash('Serviço cadastrado com sucesso!', 'success')
                return redirect(url_for('cadastrar_servico'))

        except Exception as e:
            flash(f'Erro ao cadastrar serviço: {e}', 'danger')

    return render_template('servico_form.html', servico=None)

#================== BANCOS =========================

@app.route('/atualizar_backups', methods=['GET', 'POST'])
@login_required
def atualizar_backups():
    global backups_em_dia, backups_atrasados, backups_sem_registro

    backups = []
    backups_em_dia = 0
    backups_atrasados = 0
    backups_sem_registro = 0

    try:

        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:

            # Buscar os backups
            cursor.execute(
                "SELECT nome, drive_link ,ultimo_backup, data_ult_bckp FROM clientes WHERE drive_link IS NOT NULL AND drive_link != ' ' order by data_ult_bckp")


            for row in cursor.fetchall():

                if row['ultimo_backup']:
                    try:
                        backup_datetime = datetime.strptime(row['data_ult_bckp'], "%d/%m/%Y %H:%M")
                        backup_date = backup_datetime.date()
                        current_date = datetime.now().date()

                        atrasado = current_date > (backup_date + timedelta(days=1))

                        # Incrementa os contadores
                        if atrasado:
                            backups_atrasados += 1
                        else:
                            backups_em_dia += 1

                        backups.append({
                            'nome': row['nome'],
                            'drive_link': row['drive_link'],
                            'ultimo_backup': row['ultimo_backup'],
                            'data_ult_bckp': row['data_ult_bckp'],
                            'atrasado': atrasado
                        })
                    except ValueError as e:
                        print(f"Erro ao processar data para {row['ultimo_backup']}: {e}")
                else:

                    backups_sem_registro += 1

                    backups.append({
                        'nome': row['nome'],
                        'drive_link':row['drive_link'],
                        'ultimo_backup': row['ultimo_backup'],
                        'data_ult_bckp': "Sem registro",
                        'atrasado': True
                    })

    except Exception as e:
        status_message = f"Erro ao buscar backups no banco: {str(e)}"
        backups = []

    backups.sort(key=lambda x: not x['atrasado'])

    # Armazenando os valores na sessão
    session['backups_em_dia'] = backups_em_dia
    session['backups_atrasados'] = backups_atrasados

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    status_message = None

    if request.method == 'POST':

        try:
                backups_nao_atualizados = api.atualizar_backup()
                status_message = "Backups atualizados com sucesso!"

        except Exception as e:
                status_message = f"Erro ao atualizar os backups: {str(e)}"



    return render_template(
        'atualizar_backups.html',
        backups=backups,
        status_message=status_message,
        backups_em_dia=backups_em_dia,
        backups_atrasados=backups_atrasados,
        backups_sem_registro=backups_sem_registro
    )

# ================= ACOMPANHAMENTO =====================

@app.route('/acompanhamento')
@login_required
def acompanhamento():
    """Exibe a lista de clientes e seus acompanhamentos."""
    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT c.id, c.nome, a.treinamento_vendas, a.treinamento_cadastros,a.financeiro, 
                           a.treinamento_estoque, a.treinamento_relatorios, a.backup_configurado, a.portal,
                           a.data_registro,a.finalizado
                    FROM clientes c
                    LEFT JOIN acompanhamento a ON c.id = a.id_cliente
                    WHERE c.ativo = 1 AND c.acompanhamento = 1 and a.finalizado = 0
                """)
                clientes = cursor.fetchall()

        return render_template("acompanhamento.html", clientes=clientes)
    except Exception as e:
        return f"Erro ao buscar acompanhamentos: {e}"

@app.route('/acompanhamento/atualizar', methods=['POST'])
@login_required
def atualizar_acompanhamento():
    """Atualiza as informações do acompanhamento do cliente, impedindo edições em finalizados."""
    id_cliente = request.form.get("id_cliente")

    user_id = session['user_id']  # Obtém o user_id da sessão

    # Convertendo checkboxes corretamente
    treinamento_vendas = 1 if request.form.get("treinamento_vendas") else 0
    treinamento_cadastros = 1 if request.form.get("treinamento_cadastros") else 0
    treinamento_estoque = 1 if request.form.get("treinamento_estoque") else 0
    treinamento_relatorios = 1 if request.form.get("treinamento_relatorios") else 0
    financeiro = 1 if request.form.get("financeiro") else 0
    portal = 1 if request.form.get("portal") else 0
    backup_configurado = 1 if request.form.get("backup_configurado") else 0
    pendencia = request.form.get("pendencia", "").strip()

    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # 🔍 Verifica se o acompanhamento está finalizado
                cursor.execute("""
                    SELECT id, finalizado FROM acompanhamento 
                    WHERE id_cliente = %s 
                    ORDER BY data_registro DESC LIMIT 1
                """, (id_cliente,))
                acompanhamento = cursor.fetchone()

                if not acompanhamento:
                    flash("Nenhum acompanhamento encontrado para este cliente.", "warning")
                    return redirect(url_for("acompanhamento"))

                if acompanhamento["finalizado"]:  # Se estiver finalizado, bloqueia a atualização!
                    flash("Este acompanhamento já foi finalizado e não pode ser alterado.", "danger")
                    return redirect(url_for("acompanhamento")), 403  # Retorna HTTP 403 - Proibido

                # Se passou pela verificação, continua com a atualização
                id_acompanhamento = acompanhamento["id"]

                cursor.execute("""
                    UPDATE acompanhamento 
                    SET treinamento_vendas = %s,
                        treinamento_cadastros = %s,
                        treinamento_estoque = %s,
                        treinamento_relatorios = %s,
                        financeiro = %s,
                        portal = %s,
                        backup_configurado = %s
                    WHERE id = %s
                """, (treinamento_vendas, treinamento_cadastros, treinamento_estoque,
                      treinamento_relatorios,financeiro, portal, backup_configurado, id_acompanhamento))

                # Se houver pendência, registra a atualização
                if pendencia:
                    cursor.execute("""
                        INSERT INTO acompanhamento_updates (id_acompanhamento, descricao, pendencia, usuario)
                        VALUES (%s, %s, TRUE, %s)
                    """, (id_acompanhamento, pendencia, user_id))

                connection.commit()

        flash("Acompanhamento atualizado com sucesso!", "success")

    except psycopg2.Error as err:
        flash(f"Erro no Postergree: {err}", "danger")

    except Exception as e:
        flash(f"Erro inesperado: {e}", "danger")

    return redirect(url_for("acompanhamento"))

@app.route('/acompanhamento/concluir', methods=['POST'])
@login_required
def concluir_acompanhamento():
    """Marca o acompanhamento como concluído e atualiza o status do cliente."""
    id_cliente = request.form.get("id_cliente")

    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Finaliza o acompanhamento mais recente do cliente
                cursor.execute("""
                    UPDATE acompanhamento 
                    SET finalizado = TRUE 
                    WHERE id_cliente = %s AND finalizado = FALSE
                """, (id_cliente,))

                # Atualiza o status do cliente para 'não está mais em acompanhamento'
                cursor.execute("""
                    UPDATE clientes 
                    SET acompanhamento = 0 
                    WHERE id = %s
                """, (id_cliente,))

                connection.commit()

        flash("Acompanhamento concluído com sucesso!", "success")
    except psycopg2.Error as err:
        flash(f"Erro Postergree: {err}", "danger")
    except Exception as e:
        flash(f"Erro inesperado: {e}", "danger")

    return redirect(url_for("acompanhamento"))

@app.route('/acompanhamento/adicionar', methods=['POST'])
@login_required
def adicionar_acompanhamento():
    """Adiciona um novo acompanhamento para o cliente, desde que o anterior esteja finalizado."""
    id_cliente = request.form.get("id_cliente")

    if not id_cliente:
        flash("Erro: Nenhum cliente selecionado.", "danger")
        return redirect(url_for("acompanhamento"))

    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Verifica se existe um acompanhamento em andamento
                cursor.execute("""
                    SELECT id, finalizado 
                    FROM acompanhamento 
                    WHERE id_cliente = %s 
                    ORDER BY id DESC LIMIT 1
                """, (id_cliente,))
                acompanhamento_atual = cursor.fetchone()

                if acompanhamento_atual and acompanhamento_atual["finalizado"] == 0:
                    flash("Este cliente já tem um acompanhamento em andamento. Finalize antes de iniciar outro.",
                          "warning")
                else:
                    # Insere um novo acompanhamento
                    cursor.execute("""
                        INSERT INTO acompanhamento (
                            id_cliente, treinamento_vendas, treinamento_cadastros, 
                            treinamento_estoque, treinamento_relatorios, backup_configurado, portal,
                            finalizado, data_registro
                        ) VALUES (%s, 0, 0, 0, 0, 0, 0, 0, NOW())
                    """, (id_cliente,))

                    # Atualiza o status do cliente para 'em acompanhamento'
                    cursor.execute("""
                        UPDATE clientes 
                        SET acompanhamento = 1 
                        WHERE id = %s
                    """, (id_cliente,))

                    connection.commit()
                    flash("Novo acompanhamento iniciado!", "success")

    except psycopg2.Error as err:
        flash(f"Erro Postergree: {err}", "danger")
    except Exception as e:
        flash(f"Erro inesperado: {e}", "danger")

    return redirect(url_for("acompanhamento"))

@app.route('/acompanhamento/buscar_cliente', methods=['GET'])
@login_required
def buscar_cliente_acompanhamento():
    """Retorna uma lista de clientes filtrados pelo nome em JSON."""
    nome_cliente = request.args.get("nome_cliente", "").strip()

    if not nome_cliente:
        return jsonify([])  # Retorna vazio se não houver nome

    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT id, nome FROM clientes WHERE nome LIKE %s and ativo = 1 LIMIT 10 ", (f"%{nome_cliente}%",))
                clientes = cursor.fetchall()

        return jsonify(clientes)

    except psycopg2.Error as err:
        return jsonify({"erro": f"Erro Postergree: {err}"})

@app.route('/acompanhamento/mensagens/<int:id_cliente>', methods=['GET'])
@login_required
def buscar_mensagens_acompanhamento(id_cliente):
    """Retorna as mensagens do acompanhamento de um cliente específico."""
    print(id_cliente)
    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Primeiro, pegamos o ID do acompanhamento pelo ID do cliente
                cursor.execute("""
                    SELECT * FROM acompanhamento WHERE id_cliente = %s and finalizado = 0
                """, (id_cliente,))
                acompanhamento = cursor.fetchone()
                print(acompanhamento)
                if not acompanhamento:
                    return jsonify([])  # Se não houver acompanhamento, retorna vazio

                id_acompanhamento = acompanhamento["id"]

                # Agora pegamos as mensagens desse acompanhamento
                cursor.execute("""
                    SELECT au.id, au.descricao, au.data_update, au.usuario
                    FROM acompanhamento_updates au
                    WHERE au.id_acompanhamento = %s
                    ORDER BY au.data_update DESC
                """, (id_acompanhamento,))

                mensagens = cursor.fetchall()

        return jsonify(mensagens)

    except psycopg2.Error as err:
        return jsonify({"erro": f"Erro Postergree: {err}"}), 500
    except Exception as e:
        return jsonify({"erro": f"Erro inesperado: {e}"}), 500

# ================= DEMANDAS =======================

@app.route('/demandas_atendimentos', methods=['GET', 'POST'])
@login_required
def demandas_atendimentos():
    if request.method == 'GET':
        try:

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                cursor.execute("""
                    SELECT a.id, a.data_atendimento, a.observacao, c.nome AS cliente, s.nome AS servico
                    FROM atendimentos a
                    INNER JOIN clientes c ON c.id = a.id_cliente
                    INNER JOIN servicos s ON s.id = a.id_servico
                    WHERE a.resolvido = 0
                """)
                demandas_pendentes = cursor.fetchall()

        except Exception as e:
            return f"Erro ao conectar ao banco de dados: {e}"

        return render_template('demandas_atendimentos.html', demandas_pendentes=demandas_pendentes)

    elif request.method == 'POST':
        try:
            demanda_id = request.form['demanda_id']

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:

                cursor.execute("UPDATE atendimentos SET resolvido = 1, data_resolucao = %s WHERE id = %s", (datetime.now(),demanda_id,))
                connection.commit()

                return redirect(url_for('demandas_atendimentos'))

        except Exception as e:
            return f"Erro ao marcar demanda como resolvida: {e}"

#================== CALCULADORA =====================

@app.route('/calculadora', methods=['GET', 'POST'])
@login_required
def calculadora():
    resultado = None
    dias_atraso = 0
    multa = 0.0
    juros = 0.0
    valor_final = 0.0
    data_hoje = date.today().strftime('%d/%m/%Y')  # Formato brasileiro
    valor_original = 0.0
    data_boleto = ""

    if request.method == 'POST':
        data_boleto = request.form.get('data_boleto')
        valor_original = float(request.form.get('valor_original', 0))

        if data_boleto and valor_original:
            data_boleto_obj = datetime.strptime(data_boleto, '%Y-%m-%d').date()
            dias_atraso = (date.today() - data_boleto_obj).days

            if dias_atraso > 0:
                multa = round((valor_original * 2) / 100, 2)
                juros = round((dias_atraso * 0.33) / 100 * valor_original, 2)
                valor_final = round(valor_original + multa + juros, 2)
            else:
                valor_final = valor_original

            # Converter data_boleto para string no formato brasileiro para exibição
            data_boleto = data_boleto_obj.strftime('%d/%m/%Y')

            resultado = True

    return render_template('calculadora.html', data_boleto=data_boleto, data_hoje=data_hoje, resultado=resultado,
                           dias_atraso=dias_atraso, multa=multa, juros=juros, valor_final=valor_final, valor_original=valor_original)

#================== VERSOES =========================

@app.route('/versoes/novo', methods=['GET', 'POST'])
@login_required
def cadastrar_versao():
    if request.method == 'POST':
        # Captura os dados do formulário
        versao = request.form.get('versao')
        pi = request.form.get('pi')

        # Verifica se os campos foram preenchidos
        if not versao or not pi:
            flash('Os campos "Versão" e "PI" são obrigatórios!', 'danger')
            return render_template('versao_form.html', versao=None)

        try:
            # Conexão com o banco de dados
            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Inserção no banco de dados
                cursor.execute("""
                    INSERT INTO versoes (versao, pi)
                    VALUES (%s, %s)
                """, (versao, pi))
                connection.commit()

                # Exibe mensagem de sucesso
                flash('Versão cadastrada com sucesso!', 'success')
                return redirect(url_for('cadastrar_versao'))

        except Exception as e:
            flash(f'Erro ao cadastrar versão: {e}', 'danger')

    return render_template('versao_form.html', versao=None)



#==================START=============================

if __name__ == '__main__':
    testar_conec()
    criar_tabela_servicos()
    criar_tabela_usuarios()
    criar_tabela_escalas()
    criar_tabela_atendimentos()
    criar_tabela_checklist()
    criar_tabela_clientes()
    criar_tabela_backups()
    criar_tabela_acompanhamento()
    criar_tabela_acompanhamento_updates()
    criar_tabela_versoes()
    app.run(debug= True, host='0.0.0.0', port=5000)