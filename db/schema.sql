-- Esquema de la base de datos lostnet_db usado por las pruebas de integración.
-- Contiene solo la estructura (sin datos) de las tablas que utiliza la API.
CREATE DATABASE IF NOT EXISTS lostnet_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lostnet_db;

CREATE TABLE IF NOT EXISTS t1_users (
    email      VARCHAR(255) PRIMARY KEY,
    user_id    VARCHAR(255),
    last_lat   DECIMAL(10, 7),
    last_lon   DECIMAL(10, 7)
);

CREATE TABLE IF NOT EXISTS report_index (
    id                VARCHAR(32) PRIMARY KEY,
    user_id           VARCHAR(255),
    email             VARCHAR(255),
    desc_short        VARCHAR(500),
    category          VARCHAR(100),
    lat               DECIMAL(10, 7),
    lon               DECIMAL(10, 7),
    status            VARCHAR(20) DEFAULT 'LOST',
    photo_url         VARCHAR(500),
    phone             TEXT,
    security_question VARCHAR(500),
    security_answer   TEXT,
    status_logico     VARCHAR(20) DEFAULT 'ACTIVO',
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_report_email (email),
    INDEX idx_report_created (created_at)
);

CREATE TABLE IF NOT EXISTS report_rate_events (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_rate_email_created (email, created_at)
);

CREATE TABLE IF NOT EXISTS report_purge_queue (
    report_id VARCHAR(32) PRIMARY KEY,
    photo_url VARCHAR(500),
    queued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t7_buzon (
    id        VARCHAR(32) PRIMARY KEY,
    to_email  VARCHAR(255),
    title     VARCHAR(255),
    message   TEXT,
    INDEX idx_buzon_email (to_email)
);

CREATE TABLE IF NOT EXISTS t8_comentarios (
    id         VARCHAR(32) PRIMARY KEY,
    report_id  VARCHAR(32),
    user_name  VARCHAR(255),
    text       TEXT,
    timestamp  BIGINT,
    INDEX idx_com_report (report_id)
);

CREATE TABLE IF NOT EXISTS puntos_seguros (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(255),
    lat           DECIMAL(10, 7),
    lon           DECIMAL(10, 7),
    tipo          VARCHAR(100),
    status_logico VARCHAR(20) DEFAULT 'ACTIVO'
);

CREATE TABLE IF NOT EXISTS frag_usuarios_sabuesos (
    email       VARCHAR(255) PRIMARY KEY,
    user_type   VARCHAR(50),
    badge       VARCHAR(100),
    joined_date VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS frag_usuarios_perdedores (
    email       VARCHAR(255) PRIMARY KEY,
    user_type   VARCHAR(50),
    badge       VARCHAR(100),
    joined_date VARCHAR(50)
);
