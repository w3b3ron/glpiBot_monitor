# 📊 glpiBot_monitor

Sistema executivo para **monitoramento, relatórios em HTML e gestão de chamados do GLPI** via Telegram e E-mail (SMTP), desenvolvido exclusivamente para **Gestores e Coordenadores de TI**.

---

## 🎯 Funcionalidades Principais

- **Uso Exclusivo para Gestores**: Gate de segurança que valida os gestores autorizados por Telegram ID.
- **Notificação Interativa por Telegram**: Nos horários agendados (ex: 07:30 e 18:00) ou via comando, o bot notifica o gestor no Telegram oferecendo o relatório com botões interativos (`[ 📧 Sim, enviar para meu e-mail ]` / `[ ❌ Agora não ]`).
- **Envio de Relatórios HTML por E-mail**: Somente após a confirmação do gestor, o sistema gera um relatório em **HTML responsivo e estilizado** e o envia diretamente para o e-mail cadastrado daquele gestor.
- **Métricas Executivas de ITSM**:
  - Totalizadores de chamados (Abertos, Criados Hoje, Resolvidos Hoje, MTTR).
  - Tabela de Chamados Sem Técnico Atribuído (gargalos de delegação).
  - Tabela de Chamados Críticos em Atraso (> 48h / SLA).
  - Distribuição da carga de trabalho por técnico.
- **Operação Read-Only Otimizada**: Conecta-se ao MySQL do GLPI utilizando conexões assíncronas em modo apenas leitura, garantindo total segurança contra alteração de dados do GLPI.

---

## 📂 Estrutura do Projeto

```
glpiBot_monitor/
├── .env.example              # Modelo de variáveis de ambiente
├── .gitignore                # Arquivo gitignore seguro
├── main.py                   # Ponto de entrada assíncrono (python main.py)
├── managers.example.json     # Modelo do dicionário de gestores autorizados
├── managers.json             # Mapeamento local (Telegram ID -> Email Gestor)
├── README.md                 # Documentação do projeto
├── requirements.txt          # Dependências do projeto
└── app/                      # Módulo principal (código-fonte)
    ├── __init__.py
    ├── bot.py                # Telegram Bot e Handlers unificados
    ├── config.py             # Carregamento de variáveis do .env e gestores
    ├── database.py           # Conexão assíncrona MySQL (aiomysql)
    ├── email_service.py      # Renderização do HTML e envio por SMTP
    ├── queries.py            # Consultas SQL para KPIs e relatórios
    ├── report_service.py     # Orquestrador de busca e geração de dados
    ├── scheduler.py          # Agendador periódico de notificações
    └── security.py           # Gate de autorização dos gestores
```

---

## 🚀 Como Configurar e Executar

### 1. Requisitos
- Python 3.9+
- Acesso de leitura ao banco de dados MySQL do GLPI.
- Conta/Servidor SMTP para envio de e-mails (ex: Gmail, Outlook, SMTP corporativo).
- Token de Bot do Telegram criado no `@BotFather`.

### 2. Instalação das Dependências
```bash
# Crie e ative o ambiente virtual (opcional)
python -m venv .venv
# Windows:
.venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Configuração do `.env`
Copie o arquivo `.env.example` para `.env` e preencha as credenciais:
```bash
cp .env.example .env
```
Variáveis principais:
- `BOT_TOKEN`: Token do Telegram do `@BotFather`.
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: Dados de acesso ao MySQL do GLPI.
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: Servidor e senha de app de e-mail.

### 4. Configuração dos Gestores (`managers.json`)
Edite o arquivo `managers.json` associando os **Telegram User IDs** aos dados dos gestores:
```json
{
  "123456789": {
    "nome": "Weber Nascimento",
    "email": "weber.nascimento@empresa.com.br",
    "cargo": "Gestor de TI",
    "ativo": true
  }
}
```
*Nota*: Caso o gestor use o bot sem ter o e-mail no arquivo, poderá cadastrá-lo diretamente pelo chat usando o comando `/cadastrar_email seu.email@empresa.com.br`.

### 5. Execução
```bash
python main.py
```

---

## 💬 Comandos Disponíveis no Telegram

- `/start` ou `/menu`: Exibe o menu principal de gestor.
- `/relatorio`: Apresenta o prompt com botão interativo para envio do relatório HTML ao seu e-mail.
- `/status`: Consulta métricas rápidas de KPIs diretamente na tela do Telegram.
- `/cadastrar_email email@empresa.com`: Atualiza seu endereço de e-mail de destino no sistema.
- `/help`: Exibe guia de suporte aos gestores.
