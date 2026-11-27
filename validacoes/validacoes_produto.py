from decimal import Decimal, InvalidOperation
from werkzeug.utils import secure_filename

CATEGORIAS = ['Informática', 'Periféricos', 'Áudio', 'Acessórios', 'Outros']
EXTENSOES_FOTO = {'jpg', 'jpeg', 'png', 'webp'}


def converter_preco(valor):
    valor = (valor or '').strip()
    if not valor or '.' in valor and ',' not in valor:
        return None
    limpo = valor.replace('.', '').replace(',', '.')
    try:
        numero = Decimal(limpo)
        if numero <= 0 or numero > Decimal('99999999.99'):
            return None
        return numero.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return None


def extensao_da_foto(nome):
    nome = secure_filename(nome or '')
    return nome.rsplit('.', 1)[1].lower() if '.' in nome else ''


def validar_produto(dados, foto=None):
    erros = []
    nome = dados.get('nome', '').strip()
    if not 3 <= len(nome) <= 255:
        erros.append('O nome deve ter entre 3 e 255 caracteres.')
    if len(dados.get('descricao', '').strip()) > 2000:
        erros.append('A descrição deve ter no máximo 2000 caracteres.')
    if converter_preco(dados.get('preco')) is None:
        erros.append('Informe um preço brasileiro maior que zero e válido.')
    try:
        estoque = int(dados.get('estoque', ''))
        if not 0 <= estoque <= 1000000:
            raise ValueError
    except (ValueError, TypeError):
        erros.append('O estoque deve ser um inteiro entre 0 e 1.000.000.')
    if dados.get('categoria') and dados['categoria'] not in CATEGORIAS:
        erros.append('Selecione uma categoria válida.')
    if foto and foto.filename and extensao_da_foto(foto.filename) not in EXTENSOES_FOTO:
        erros.append('A foto deve ser JPG, JPEG, PNG ou WEBP.')
    return erros
