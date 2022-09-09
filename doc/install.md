O Monitor Twitter funciona com Python 3.6, Django 1.2 e banco MySQL/MariaDb 
Sob Debian 9 ou Ubuntu 18.04 ou superior

sudo apt install pkg-config

A criação do banco MySQL deve utilizar o collate mais geral para aceitar emojis: 

CREATE DATABASE twitsearch DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;