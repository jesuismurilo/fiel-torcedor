-- DROP DATABASE IF EXISTS fiel_torcedor;   -- tire o "--" só se quiser apagar tudo e recomeçar do zero

CREATE DATABASE IF NOT EXISTS fiel_torcedor
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE fiel_torcedor;

-- perfis vem antes de usuarios, porque usuarios aponta para ele (chave estrangeira).
CREATE TABLE IF NOT EXISTS perfis (
    id_perfil     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome          VARCHAR(100) NOT NULL UNIQUE,
    descricao     VARCHAR(255),
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deletado_em   DATETIME NULL                         -- soft-delete: o registro some das telas, mas continua no banco
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    senha           VARCHAR(255) NOT NULL,      -- guarda o HASH, nunca a senha
    celular         VARCHAR(20),
    data_nascimento DATE,
    cpf             VARCHAR(14) UNIQUE,         -- gravado como 000.000.000-00
    perfil_id       BIGINT UNSIGNED NOT NULL,
    cep             VARCHAR(9),
    endereco        VARCHAR(255),
    numero          VARCHAR(20),
    complemento     VARCHAR(100),
    cidade          VARCHAR(100),
    estado          CHAR(2),
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deletado_em     DATETIME NULL,
    CONSTRAINT fk_usuarios_perfis
        FOREIGN KEY (perfil_id) REFERENCES perfis (id_perfil)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- valor e desconto continuam como texto para aceitar formatos como "R$ 24,50/mês" e "50%".
CREATE TABLE IF NOT EXISTS planos (
    id_plano      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome          VARCHAR(100) NOT NULL,
    valor         VARCHAR(40) NOT NULL,
    setor         VARCHAR(100),
    desconto      VARCHAR(20),
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deletado_em   DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ingressos (
    id_ingresso   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    partida       VARCHAR(150) NOT NULL,
    data_jogo     DATE NOT NULL,
    estadio       VARCHAR(120),
    preco_base    VARCHAR(40),
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deletado_em   DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Perfis iniciais (os mesmos dois níveis que o cadastro de usuários já tinha).
-- INSERT IGNORE: pode rodar o script de novo sem duplicar.
INSERT IGNORE INTO perfis (nome, descricao) VALUES
    ('Administrador', 'Acesso a todas as áreas do painel'),
    ('Gerente',       'Acesso às consultas e aos usuários'),
    ('Usuário',       'Acesso de consulta');

-- Primeiro acesso de desenvolvimento: admin@fieltorcedor.local / Admin123
-- Troque a senha depois do primeiro login em um ambiente real.
INSERT IGNORE INTO usuarios (nome, email, senha, perfil_id)
SELECT 'Administrador inicial', 'admin@fieltorcedor.local',
       'scrypt:32768:8:1$MJndap3L5YlZiiCJ$79adddfefda9c11f98f531f89d736aef735771d5587b0241cf489b2dc1a35097ec63001c801839454182dc8c7cd6d9f6ded2a10856afd256c7369247ec48cf3e',
       id_perfil FROM perfis WHERE nome = 'Administrador' AND deletado_em IS NULL;

CREATE TABLE IF NOT EXISTS produtos (
    id_produto BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,
    categoria VARCHAR(100),
    preco DECIMAL(10,2) NOT NULL,
    estoque INT UNSIGNED NOT NULL DEFAULT 0,
    foto VARCHAR(255),
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
