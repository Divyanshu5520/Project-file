-- Create database (run once)
CREATE DATABASE IF NOT EXISTS face_protection;
USE face_protection;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    name VARCHAR(255) PRIMARY KEY,
    embedding LONGBLOB,
    lockout_time BIGINT DEFAULT 0,
    role ENUM('user', 'admin') DEFAULT 'user'
);

-- File keys table to store encryption keys per user-file pair
CREATE TABLE IF NOT EXISTS file_keys (
    username VARCHAR(255),
    file_path VARCHAR(1024),
    key BLOB,
    PRIMARY KEY (username, file_path),
    FOREIGN KEY (username) REFERENCES users(name) ON DELETE CASCADE
);
