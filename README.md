# Fiel Torcedor Flask

Aplicação Flask/MySQL para administrar usuários, perfis, planos do sócio-torcedor, partidas/ingressos e produtos.

## Primeiro acesso em banco novo

O `banco.sql` cria os perfis Administrador, Gerente e Usuário e também um administrador inicial:

- E-mail: `admin@fieltorcedor.local`
- Senha: `Admin123`

Troque a senha depois do primeiro acesso. Essa credencial é apenas para desenvolvimento local.

## Módulos e rotas

- Autenticação: `/`, `/login` e `/logout` somente por `POST`.
- Painel: `/dashboard`.
- Perfis: `/perfis`, `/perfis/inserir`, `/perfis/<id>/editar`, exclusão por `POST`, `/perfis/lixeira` (botão **Lixeira** na lista de perfis) e restauração. Os perfis Administrador, Gerente e Usuário são usados nas permissões e por isso não podem ser renomeados nem excluídos.
- Usuários: `/usuarios`, `/usuarios/inserir`, `/usuarios/<id>`, edição e exclusão por `POST`.
- Planos: `/planos/listar`, `/planos/inserir` e exclusão por `POST`.
- Ingressos: `/ingressos/listar`, `/ingressos/inserir` e exclusão por `POST`.
- Produtos: `/produtos`, `/produtos/inserir`, edição e exclusão por `POST`.

O dashboard conta todos os produtos cadastrados, independentemente do campo `ativo`, e mostra os cards e a tabela de últimos usuários apenas para os perfis que têm acesso a essas áreas. Planos e ingressos permanecem protegidos por login e visíveis no menu.

## Configuração

1. Inicie o MySQL/MariaDB e execute `banco.sql` no phpMyAdmin.
2. Copie `.env.example` para `.env` e informe host, porta, usuário, senha, banco e `SECRET_KEY`.
3. Instale as dependências com `pip install -r requirements.txt`.
4. Inicie com `python app.py` e acesse `http://127.0.0.1:5000`.

## Validações e segurança

Os dados são normalizados antes da validação: textos são limpos, e-mails são convertidos para minúsculas e campos opcionais vazios viram `None`. Usuários têm validação de senha, confirmação, CPF, e-mail, celular, CEP, data, UF e perfil. Produtos aceitam preço brasileiro com `Decimal`, estoque limitado, categorias permitidas e imagens JPG/JPEG/PNG/WEBP de até 2 MB. Todo formulário `POST` usa CSRF.

## Exclusão

Perfis usam soft delete, com lixeira e restauração. Usuários seguem o `DELETE` físico do Capítulo 16; por isso uma pessoa excluída pode ser cadastrada novamente com o mesmo e-mail ou CPF. Produtos, planos e ingressos também têm exclusão física ou lógica conforme seus fluxos: produtos são removidos fisicamente com suas fotos, enquanto planos e ingressos são marcados em `deletado_em`.

## Verificação local

Use `python -m compileall -q .` para validar a sintaxe e carregue o banco para executar os testes funcionais de login, CSRF, permissões, CRUDs, filtros, paginação, uploads e reingresso de usuários excluídos.
