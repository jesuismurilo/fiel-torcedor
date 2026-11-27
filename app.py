import os
import uuid
from datetime import datetime
from decimal import Decimal
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

from db import execute_insert, execute_one, execute_query
from validacoes.validacoes_perfil import validar_perfil
from validacoes.validacoes_produto import CATEGORIAS, EXTENSOES_FOTO, converter_preco, extensao_da_foto, validar_produto
from validacoes.validacoes_usuario import (
    UFS, formatar_celular, formatar_cep, formatar_cpf, normalizar_usuario, validar_usuario,
)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('Defina SECRET_KEY no arquivo .env (veja o .env.example).')

CSRFProtect(app)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# As permissões comparam o NOME do perfil; por isso estes três nomes não podem ser alterados nem excluídos.
PERFIS_FIXOS = ('Administrador', 'Gerente', 'Usuário')

PASTA_UPLOADS = Path(app.root_path) / 'static' / 'uploads'
PASTA_UPLOADS.mkdir(parents=True, exist_ok=True)

SELECT_USUARIO = '''
SELECT u.id_usuario, u.nome, u.email, u.celular, u.data_nascimento, u.cpf,
       u.perfil_id, u.cep, u.endereco, u.numero, u.complemento, u.cidade,
       u.estado, u.criado_em, u.atualizado_em,
       p.nome AS perfil, p.descricao AS perfil_descricao
FROM usuarios u JOIN perfis p ON p.id_perfil = u.perfil_id
WHERE u.deletado_em IS NULL
'''


def login_required(func):
    @wraps(func)
    def envolvida(*args, **kwargs):
        if 'id_usuario' not in session:
            flash('Entre para continuar.', 'warning')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return envolvida


def perfil_required(*permitidos):
    def decorador(func):
        @wraps(func)
        def envolvida(*args, **kwargs):
            if session.get('perfil') not in permitidos:
                abort(403)
            return func(*args, **kwargs)
        return envolvida
    return decorador


def texto(campo):
    return request.form.get(campo, '').strip()


def opcional(campo):
    return texto(campo) or None


def perfis_ativos():
    return execute_query('SELECT id_perfil, nome FROM perfis WHERE deletado_em IS NULL ORDER BY nome', fetch=True)


def formatar_numero(valor):
    numero = Decimal(str(valor))
    return f'{numero:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


@app.template_filter('data_br')
def data_br(valor):
    return valor.strftime('%d/%m/%Y') if valor else '—'


@app.template_filter('data_hora_br')
def data_hora_br(valor):
    return valor.strftime('%d/%m/%Y às %H:%M') if valor else '—'


@app.template_filter('cpf_oculto')
def cpf_oculto(valor):
    return f'***.{valor[4:11]}-**' if valor else '—'


@app.template_filter('moeda')
def moeda(valor):
    if valor is None:
        return 'R$ 0,00'
    return f'R$ {formatar_numero(valor)}'


@app.route('/')
def inicio():
    return redirect(url_for('dashboard' if 'id_usuario' in session else 'login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'id_usuario' in session:
        return redirect(url_for('dashboard'))
    email = ''
    if request.method == 'POST':
        email = texto('email').lower()
        senha = request.form.get('senha', '')
        usuario = execute_one('''SELECT u.id_usuario, u.nome, u.senha, p.nome AS perfil
            FROM usuarios u JOIN perfis p ON p.id_perfil = u.perfil_id
            WHERE u.email = %s AND u.deletado_em IS NULL''', (email,))
        if usuario and check_password_hash(usuario['senha'], senha):
            session.clear()
            session.update(id_usuario=usuario['id_usuario'], nome=usuario['nome'], perfil=usuario['perfil'])
            flash(f'Você entrou como {usuario["nome"]}.', 'success')
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html', email=email)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    totais = execute_one('''SELECT
      (SELECT COUNT(*) FROM usuarios WHERE deletado_em IS NULL) usuarios,
      (SELECT COUNT(*) FROM perfis WHERE deletado_em IS NULL) perfis,
      (SELECT COUNT(*) FROM produtos) produtos''')
    ultimos = []
    if session.get('perfil') in ('Administrador', 'Gerente'):
        ultimos = execute_query(SELECT_USUARIO + ' ORDER BY u.id_usuario DESC LIMIT 5', fetch=True)
    return render_template('dashboard.html', totais=totais, ultimos_usuarios=ultimos)


@app.route('/perfis')
@login_required
@perfil_required('Administrador')
def listar_perfis():
    busca = request.args.get('busca', '').strip()
    descricao = request.args.get('descricao', '')
    ordem = request.args.get('ordem', 'nome')
    if ordem not in {'nome', 'recentes'}:
        ordem = 'nome'
    cond = ' WHERE deletado_em IS NULL'
    params = []
    if busca:
        cond += ' AND (nome LIKE %s OR descricao LIKE %s)'
        params += [f'%{busca}%', f'%{busca}%']
    if descricao == 'com':
        cond += ' AND descricao IS NOT NULL'
    elif descricao == 'sem':
        cond += ' AND descricao IS NULL'
    order_sql = 'nome ASC' if ordem == 'nome' else 'criado_em DESC, id_perfil DESC'
    total = execute_one('SELECT COUNT(*) AS total FROM perfis' + cond, tuple(params))['total']
    paginas = max(1, (total + 9) // 10)
    pagina = max(1, min(request.args.get('pagina', 1, type=int) or 1, paginas))
    perfis = execute_query(
        'SELECT id_perfil, nome, descricao, criado_em, atualizado_em FROM perfis'
        + cond + ' ORDER BY ' + order_sql + ' LIMIT %s OFFSET %s',
        tuple(params + [10, (pagina - 1) * 10]),
        fetch=True,
    )
    return render_template(
        'perfis/perfis_lista.html',
        perfis=perfis, busca=busca, descricao=descricao, ordem=ordem,
        pagina=pagina, total=total, total_paginas=paginas,
    )


@app.route('/perfis/inserir', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def inserir_perfil():
    dados = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        nome, descricao = texto('nome'), opcional('descricao')
        erros = validar_perfil(nome, descricao)
        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template('perfis/perfil_form.html', dados=dados, acao='criar')
        try:
            execute_insert('INSERT INTO perfis (nome, descricao) VALUES (%s, %s)', (nome, descricao))
        except IntegrityError as erro:
            if erro.errno == 1062:
                flash('Já existe um perfil com este nome (ele pode estar na lixeira).', 'danger')
                return render_template('perfis/perfil_form.html', dados=dados, acao='criar')
            raise
        flash(f'Perfil "{nome}" cadastrado.', 'success')
        return redirect(url_for('listar_perfis'))
    return render_template('perfis/perfil_form.html', dados=dados, acao='criar')


@app.route('/perfis/<int:id_perfil>/editar', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def editar_perfil(id_perfil):
    perfil = execute_one('SELECT id_perfil, nome, descricao FROM perfis WHERE id_perfil=%s AND deletado_em IS NULL', (id_perfil,))
    if not perfil:
        abort(404)
    dados = request.form if request.method == 'POST' else perfil
    if request.method == 'POST':
        nome, descricao = texto('nome'), opcional('descricao')
        erros = validar_perfil(nome, descricao, id_perfil)
        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template('perfis/perfil_form.html', dados=dados, acao='editar', id_perfil=id_perfil)
        if perfil['nome'] in PERFIS_FIXOS and nome != perfil['nome']:
            flash(f'O perfil "{perfil["nome"]}" é usado nas permissões do sistema e não pode ser renomeado.', 'danger')
            return render_template('perfis/perfil_form.html', dados=dados, acao='editar', id_perfil=id_perfil)
        try:
            execute_query('UPDATE perfis SET nome=%s, descricao=%s WHERE id_perfil=%s', (nome, descricao, id_perfil))
        except IntegrityError as erro:
            if erro.errno == 1062:
                flash('Já existe um perfil com este nome (ele pode estar na lixeira).', 'danger')
                return render_template('perfis/perfil_form.html', dados=dados, acao='editar', id_perfil=id_perfil)
            raise
        flash(f'Perfil "{nome}" atualizado.', 'success')
        return redirect(url_for('listar_perfis'))
    return render_template('perfis/perfil_form.html', dados=dados, acao='editar', id_perfil=id_perfil)


@app.route('/perfis/<int:id_perfil>/excluir', methods=['POST'])
@login_required
@perfil_required('Administrador')
def excluir_perfil(id_perfil):
    perfil = execute_one('SELECT id_perfil, nome FROM perfis WHERE id_perfil=%s AND deletado_em IS NULL', (id_perfil,))
    if not perfil:
        abort(404)
    em_uso = execute_one('SELECT COUNT(*) AS total FROM usuarios WHERE perfil_id=%s AND deletado_em IS NULL', (id_perfil,))
    if perfil['nome'] in PERFIS_FIXOS:
        flash(f'O perfil "{perfil["nome"]}" é usado nas permissões do sistema e não pode ser excluído.', 'warning')
    elif em_uso['total']:
        flash(f'O perfil "{perfil["nome"]}" está em uso e não pode ser excluído.', 'warning')
    else:
        execute_query('UPDATE perfis SET deletado_em=NOW() WHERE id_perfil=%s', (id_perfil,))
        flash(f'Perfil "{perfil["nome"]}" enviado para a lixeira.', 'success')
    return redirect(url_for('listar_perfis'))


@app.route('/perfis/lixeira')
@login_required
@perfil_required('Administrador')
def lixeira_perfis():
    perfis = execute_query('SELECT id_perfil, nome, descricao, deletado_em FROM perfis WHERE deletado_em IS NOT NULL ORDER BY deletado_em DESC', fetch=True)
    return render_template('perfis/perfis-lixeira.html', perfis=perfis)


@app.route('/perfis/<int:id_perfil>/restaurar', methods=['POST'])
@login_required
@perfil_required('Administrador')
def restaurar_perfil(id_perfil):
    perfil = execute_one('SELECT id_perfil, nome FROM perfis WHERE id_perfil=%s AND deletado_em IS NOT NULL', (id_perfil,))
    if not perfil:
        abort(404)
    if execute_one('SELECT id_perfil FROM perfis WHERE nome=%s AND deletado_em IS NULL', (perfil['nome'],)):
        flash('Já existe um perfil ativo com este nome.', 'danger')
    else:
        execute_query('UPDATE perfis SET deletado_em=NULL WHERE id_perfil=%s', (id_perfil,))
        flash('Perfil restaurado.', 'success')
    return redirect(url_for('lixeira_perfis'))


@app.route('/usuarios')
@login_required
@perfil_required('Administrador', 'Gerente')
def listar_usuarios():
    usuarios = execute_query(SELECT_USUARIO + ' ORDER BY u.nome', fetch=True)
    return render_template('usuarios/usuarios_lista.html', usuarios=usuarios)


@app.route('/usuarios/inserir', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def inserir_usuario():
    perfis = perfis_ativos()
    dados = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        dados = normalizar_usuario(request.form.to_dict())
        erros = validar_usuario(dados)
        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='criar', ufs=UFS)
        try:
            novo = execute_insert(
                '''INSERT INTO usuarios (nome, email, senha, celular, data_nascimento, cpf, perfil_id,
                   cep, endereco, numero, complemento, cidade, estado)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (
                    dados['nome'].strip(), dados['email'].strip().lower(),
                    generate_password_hash(dados['senha']),
                    formatar_celular(dados.get('celular')),
                    dados.get('data_nascimento') or None,
                    formatar_cpf(dados.get('cpf')),
                    int(dados['perfil_id']),
                    formatar_cep(dados.get('cep')),
                    dados.get('endereco') or None, dados.get('numero') or None,
                    dados.get('complemento') or None, dados.get('cidade') or None,
                    dados.get('estado') or None,
                ),
            )
        except IntegrityError as erro:
            if erro.errno == 1062:
                flash('Já existe um usuário com este e-mail ou CPF.', 'danger')
                return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='criar', ufs=UFS)
            raise
        flash(f'Usuário cadastrado (código {novo}).', 'success')
        return redirect(url_for('listar_usuarios'))
    return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='criar', ufs=UFS)


@app.route('/usuarios/<int:id_usuario>')
@login_required
@perfil_required('Administrador', 'Gerente')
def detalhar_usuario(id_usuario):
    usuario = execute_one(SELECT_USUARIO + ' AND u.id_usuario=%s', (id_usuario,))
    if not usuario:
        abort(404)
    return render_template('usuarios/usuario-detalhe.html', usuario=usuario)


@app.route('/usuarios/<int:id_usuario>/editar', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def editar_usuario(id_usuario):
    existente = execute_one(SELECT_USUARIO + ' AND u.id_usuario=%s', (id_usuario,))
    if not existente:
        abort(404)
    perfis = perfis_ativos()
    dados = request.form.to_dict() if request.method == 'POST' else existente
    if request.method == 'POST':
        erros = validar_usuario(dados, id_usuario)
        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='editar', id_usuario=id_usuario, ufs=UFS)
        valores = [
            dados.get('nome', '').strip(), dados.get('email', '').strip().lower(),
            formatar_celular(dados.get('celular')), dados.get('data_nascimento') or None,
            formatar_cpf(dados.get('cpf')), int(dados['perfil_id']),
            formatar_cep(dados.get('cep')), dados.get('endereco') or None,
            dados.get('numero') or None, dados.get('complemento') or None,
            dados.get('cidade') or None, dados.get('estado') or None,
        ]
        sql = (
            'UPDATE usuarios SET nome=%s, email=%s, celular=%s, data_nascimento=%s, cpf=%s, '
            'perfil_id=%s, cep=%s, endereco=%s, numero=%s, complemento=%s, cidade=%s, estado=%s'
        )
        if dados.get('senha'):
            sql += ', senha=%s'
            valores.append(generate_password_hash(dados['senha']))
        sql += ' WHERE id_usuario=%s'
        valores.append(id_usuario)
        try:
            execute_query(sql, tuple(valores))
        except IntegrityError as erro:
            if erro.errno == 1062:
                flash('Já existe outro usuário com este e-mail ou CPF.', 'danger')
                return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='editar', id_usuario=id_usuario, ufs=UFS)
            raise
        flash(f'Usuário "{dados.get("nome", "")}" atualizado.', 'success')
        return redirect(url_for('listar_usuarios'))
    return render_template('usuarios/usuario_form.html', perfis=perfis, dados=dados, acao='editar', id_usuario=id_usuario, ufs=UFS)


@app.route('/usuarios/<int:id_usuario>/excluir', methods=['POST'])
@login_required
@perfil_required('Administrador')
def excluir_usuario(id_usuario):
    if id_usuario == session['id_usuario']:
        flash('Você não pode excluir o seu próprio usuário.', 'danger')
        return redirect(url_for('listar_usuarios'))
    usuario = execute_one('SELECT id_usuario, nome FROM usuarios WHERE id_usuario=%s AND deletado_em IS NULL', (id_usuario,))
    if not usuario:
        abort(404)
    execute_query('DELETE FROM usuarios WHERE id_usuario=%s', (id_usuario,))
    flash(f'Usuário "{usuario["nome"]}" excluído.', 'success')
    return redirect(url_for('listar_usuarios'))


# PLANOS E INGRESSOS — módulos temáticos do Fiel Torcedor
@app.route('/planos/listar')
@login_required
def listar_planos():
    planos = execute_query('SELECT id_plano, nome, valor, setor, desconto FROM planos WHERE deletado_em IS NULL ORDER BY nome', fetch=True)
    return render_template('planos/planos-listar.html', planos=planos)


@app.route('/planos/inserir', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def inserir_plano():
    dados = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        nome, valor = dados.get('nome', '').strip(), dados.get('valor', '').strip()
        setor, desconto = dados.get('setor', '').strip(), dados.get('desconto', '').strip()
        if not nome or not valor:
            flash('Informe o nome e o valor do plano.', 'danger')
            return render_template('planos/planos-form.html', dados=dados)
        if len(nome) > 100 or len(valor) > 40 or len(setor) > 100 or len(desconto) > 20:
            flash('Algum campo excede o tamanho permitido (nome 100, valor 40, setor 100, desconto 20).', 'danger')
            return render_template('planos/planos-form.html', dados=dados)
        execute_insert(
            'INSERT INTO planos (nome, valor, setor, desconto) VALUES (%s, %s, %s, %s)',
            (nome, valor, setor or None, desconto or None),
        )
        flash('Plano cadastrado.', 'success')
        return redirect(url_for('listar_planos'))
    return render_template('planos/planos-form.html', dados=dados)


@app.route('/planos/<int:id_plano>/excluir', methods=['POST'])
@login_required
@perfil_required('Administrador')
def excluir_plano(id_plano):
    execute_query('UPDATE planos SET deletado_em=NOW() WHERE id_plano=%s AND deletado_em IS NULL', (id_plano,))
    flash('Plano excluído.', 'success')
    return redirect(url_for('listar_planos'))


@app.route('/ingressos/listar')
@login_required
def listar_ingressos():
    ingressos = execute_query('SELECT id_ingresso, partida, data_jogo, estadio, preco_base FROM ingressos WHERE deletado_em IS NULL ORDER BY data_jogo', fetch=True)
    return render_template('ingressos/ingressos-listar.html', ingressos=ingressos)


@app.route('/ingressos/inserir', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def inserir_ingresso():
    dados = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        partida, data_jogo = dados.get('partida', '').strip(), dados.get('data_jogo', '').strip()
        estadio, preco_base = dados.get('estadio', '').strip(), dados.get('preco_base', '').strip()
        if not partida or not data_jogo:
            flash('Informe a partida e a data do jogo.', 'danger')
            return render_template('ingressos/ingressos-form.html', dados=dados)
        try:
            datetime.strptime(data_jogo, '%Y-%m-%d')
        except ValueError:
            flash('A data do jogo é inválida.', 'danger')
            return render_template('ingressos/ingressos-form.html', dados=dados)
        if len(partida) > 150 or len(estadio) > 120 or len(preco_base) > 40:
            flash('Algum campo excede o tamanho permitido (partida 150, estádio 120, preço 40).', 'danger')
            return render_template('ingressos/ingressos-form.html', dados=dados)
        execute_insert(
            'INSERT INTO ingressos (partida, data_jogo, estadio, preco_base) VALUES (%s, %s, %s, %s)',
            (partida, data_jogo, estadio or None, preco_base or None),
        )
        flash('Partida cadastrada.', 'success')
        return redirect(url_for('listar_ingressos'))
    return render_template('ingressos/ingressos-form.html', dados=dados)


@app.route('/ingressos/<int:id_ingresso>/excluir', methods=['POST'])
@login_required
@perfil_required('Administrador')
def excluir_ingresso(id_ingresso):
    execute_query('UPDATE ingressos SET deletado_em=NOW() WHERE id_ingresso=%s AND deletado_em IS NULL', (id_ingresso,))
    flash('Partida excluída.', 'success')
    return redirect(url_for('listar_ingressos'))


@app.route('/produtos')
@login_required
def listar_produtos():
    produtos = execute_query(
        'SELECT id_produto, nome, descricao, categoria, preco, estoque, foto, ativo, criado_em, atualizado_em '
        'FROM produtos ORDER BY nome',
        fetch=True,
    )
    return render_template('produtos/produtos_lista.html', produtos=produtos)


def normalizar_produto(dados):
    normalizados = dict(dados)
    for campo in ('nome', 'descricao', 'categoria', 'preco', 'estoque'):
        normalizados[campo] = normalizados.get(campo, '').strip()
    return normalizados


def salvar_foto(arquivo):
    if not arquivo or not arquivo.filename:
        return None
    extensao = extensao_da_foto(arquivo.filename)
    if extensao not in EXTENSOES_FOTO:
        return None
    nome = f'{uuid.uuid4().hex}.{extensao}'
    arquivo.save(PASTA_UPLOADS / nome)
    return f'uploads/{nome}'


def apagar_foto(caminho):
    if caminho:
        arquivo = Path(app.root_path) / 'static' / caminho
        if arquivo.exists():
            arquivo.unlink()


@app.route('/produtos/inserir', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def inserir_produto():
    dados = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        dados = normalizar_produto(request.form.to_dict())
        arquivo = request.files.get('foto')
        erros = validar_produto(dados, arquivo)
        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template('produtos/produto_form.html', dados=dados, categorias=CATEGORIAS, acao='criar')
        foto = salvar_foto(arquivo)
        novo = execute_insert(
            'INSERT INTO produtos (nome, descricao, categoria, preco, estoque, foto, ativo) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (
                dados['nome'], dados.get('descricao') or None, dados.get('categoria') or None,
                converter_preco(dados['preco']), int(dados['estoque']), foto,
                1 if dados.get('ativo') else 0,
            ),
        )
        flash(f'Produto cadastrado (código {novo}).', 'success')
        return redirect(url_for('listar_produtos'))
    return render_template('produtos/produto_form.html', dados=dados, categorias=CATEGORIAS, acao='criar')


@app.route('/produtos/<int:id_produto>/editar', methods=['GET', 'POST'])
@login_required
@perfil_required('Administrador')
def editar_produto(id_produto):
    produto = execute_one('SELECT * FROM produtos WHERE id_produto=%s', (id_produto,))
    if not produto:
        abort(404)
    if request.method == 'GET':
        dados = dict(produto)
        dados['preco'] = formatar_numero(produto['preco'])
        return render_template(
            'produtos/produto_form.html',
            dados=dados, produto=produto, categorias=CATEGORIAS, acao='editar', id_produto=id_produto,
        )

    dados = normalizar_produto(request.form.to_dict())
    arquivo = request.files.get('foto')
    erros = validar_produto(dados, arquivo)
    if erros:
        for erro in erros:
            flash(erro, 'danger')
        return render_template(
            'produtos/produto_form.html',
            dados=dados, produto=produto, categorias=CATEGORIAS, acao='editar', id_produto=id_produto,
        )

    nova_foto = salvar_foto(arquivo) if arquivo and arquivo.filename else produto['foto']
    if dados.get('remover_foto') and not (arquivo and arquivo.filename):
        nova_foto = None
    execute_query(
        'UPDATE produtos SET nome=%s, descricao=%s, categoria=%s, preco=%s, estoque=%s, foto=%s, ativo=%s '
        'WHERE id_produto=%s',
        (
            dados['nome'], dados.get('descricao') or None, dados.get('categoria') or None,
            converter_preco(dados['preco']), int(dados['estoque']), nova_foto,
            1 if dados.get('ativo') else 0, id_produto,
        ),
    )
    if nova_foto != produto['foto']:
        apagar_foto(produto['foto'])
    flash('Produto atualizado.', 'success')
    return redirect(url_for('listar_produtos'))


@app.route('/produtos/<int:id_produto>/excluir', methods=['POST'])
@login_required
@perfil_required('Administrador')
def excluir_produto(id_produto):
    produto = execute_one('SELECT id_produto, nome, foto FROM produtos WHERE id_produto=%s', (id_produto,))
    if not produto:
        abort(404)
    execute_query('DELETE FROM produtos WHERE id_produto=%s', (id_produto,))
    apagar_foto(produto['foto'])
    flash(f'Produto "{produto["nome"]}" excluído.', 'success')
    return redirect(url_for('listar_produtos'))


@app.errorhandler(403)
def proibido(erro):
    return render_template('403.html'), 403


@app.errorhandler(404)
def pagina_nao_encontrada(erro):
    return render_template('404.html'), 404


@app.errorhandler(413)
def arquivo_grande(erro):
    return render_template('413.html'), 413


@app.errorhandler(500)
def erro_no_servidor(erro):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True)