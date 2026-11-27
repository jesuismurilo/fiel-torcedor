import re
from datetime import date, datetime

UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']


def so_digitos(valor):
    return re.sub(r'\D', '', valor or '')


def normalizar_usuario(dados):
    normalizados = dict(dados)
    for campo in ('nome', 'celular', 'data_nascimento', 'cpf', 'cep', 'endereco', 'numero', 'complemento', 'cidade', 'estado', 'perfil_id'):
        normalizados[campo] = (normalizados.get(campo) or '').strip()
    normalizados['email'] = (normalizados.get('email') or '').strip().lower()
    normalizados['senha'] = normalizados.get('senha') or ''
    normalizados['confirmacao'] = normalizados.get('confirmacao') or ''
    return normalizados


def formatar_celular(valor):
    d = so_digitos(valor)
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return valor or None


def formatar_cpf(valor):
    d = so_digitos(valor)
    return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}' if len(d) == 11 else (valor or None)


def formatar_cep(valor):
    d = so_digitos(valor)
    return f'{d[:5]}-{d[5:]}' if len(d) == 8 else (valor or None)


def cpf_valido(valor):
    d = so_digitos(valor)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(d[tamanho]):
            return False
    return True


def validar_email(email, id_usuario=0):
    erros = []
    if not email or len(email) > 255 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        erros.append('Informe um e-mail válido com domínio.')
    if not erros:
        from db import execute_one
        if execute_one('SELECT id_usuario FROM usuarios WHERE email = %s AND id_usuario <> %s AND deletado_em IS NULL', (email, id_usuario)):
            erros.append('Já existe um usuário com este e-mail.')
    return erros


def validar_usuario(dados, id_usuario=0):
    erros = []
    nome = dados.get('nome', '').strip()
    email = dados.get('email', '').strip().lower()
    senha = dados.get('senha', '')
    confirmacao = dados.get('confirmacao', '')
    perfil_id = dados.get('perfil_id', '')
    if not 3 <= len(nome) <= 255:
        erros.append('O nome deve ter entre 3 e 255 caracteres.')
    erros += validar_email(email, id_usuario)
    if id_usuario == 0 or senha or confirmacao:
        if not 8 <= len(senha) <= 128 or not re.search(r'[A-Za-z]', senha) or not re.search(r'\d', senha):
            erros.append('A senha deve ter entre 8 e 128 caracteres, com letras e números.')
        if senha != confirmacao:
            erros.append('A confirmação da senha não confere.')
    if not perfil_id.isdigit():
        erros.append('Selecione um perfil válido.')
    else:
        from db import execute_one
        if not execute_one('SELECT id_perfil FROM perfis WHERE id_perfil = %s AND deletado_em IS NULL', (int(perfil_id),)):
            erros.append('O perfil selecionado não existe.')
    cpf = dados.get('cpf', '').strip()
    if cpf and not cpf_valido(cpf):
        erros.append('Informe um CPF válido.')
    celular = dados.get('celular', '').strip()
    if celular and len(so_digitos(celular)) not in (10, 11):
        erros.append('O celular deve ter 10 ou 11 dígitos.')
    cep = dados.get('cep', '').strip()
    if cep and len(so_digitos(cep)) != 8:
        erros.append('O CEP deve ter 8 dígitos.')
    nascimento = dados.get('data_nascimento', '').strip()
    if nascimento:
        try:
            dt = datetime.strptime(nascimento, '%Y-%m-%d').date()
            if dt.year < 1900 or dt > date.today():
                erros.append('A data de nascimento deve estar entre 1900 e hoje.')
        except ValueError:
            erros.append('A data de nascimento é inválida.')
    if dados.get('estado') and dados['estado'] not in UFS:
        erros.append('Selecione uma UF válida.')
    limites = {'endereco':255, 'numero':20, 'complemento':100, 'cidade':100}
    for campo, limite in limites.items():
        if len(dados.get(campo, '').strip()) > limite:
            erros.append(f'O campo {campo} excede {limite} caracteres.')
    return erros
