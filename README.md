<div align="center">

# 🔮 Contest Oracle

Discord bot que avisa quando vai ter contest no **Codeforces**, com **reaction roles** por divisão.

</div>

## ✨ Funcionalidades

- **Notificação automática**: a cada 10 minutos o bot consulta a API do Codeforces e publica os próximos contests no canal configurado.
- **Reaction roles por divisão**: membros reagem às reações para escolher de quais divisões querem receber alertas, e o bot cria os cargos automaticamente.
  - 🔵 `Div 1/2`
  - 🟢 `Div 3`
  - 🟡 `Div 4`
- **Comando `/listdivs`**: lista os próximos contests organizados por divisão.

## 🧩 Comandos

| Comando | Perfil | Descrição |
| --- | --- | --- |
| `/setchannel #canal` | Administrador | Define o canal onde os alertas serão enviados. |
| `/reactionrole` | Administrador | Cria/garante os cargos e publica a mensagem de reaction roles. |
| `/listdivs` | Todos | Lista os próximos contests por divisão. |

## 🚀 Como rodar

### 1. Crie o bot no Discord

1. Acesse o [Developer Portal](https://discord.com/developers/applications) e crie uma aplicação.
2. Em **Bot**, gere o token e copie.
3. Em **OAuth2 → URL Generator**, marque `bot` + escopos de aplicação e selecione estas permissões:
   - `Create Expressions`
   - `Send Messages`
   - `Embed Links`
   - `Add Reactions`
   - `Manage Roles`
4. Use a URL gerada para adicionar o bot ao seu servidor.

### 2. Configure o token

```bash
cp .env.example .env
# edite o .env e cole o token
```

Ou exporte direto na sessão:

```bash
export DISCORD_TOKEN="seu-token-aqui"
```

### 3. Instale e rode

Requer **Python 3.10+**.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

O contêiner de dados (canais, contests enviados e mensagens de reação) é persistido em arquivos `.json` na mesma pasta.

### Desenvolvimento

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest
```

## 🧠 Lógica de classificação

A classificação de divisões, filtragem de contests e formatação das mensagens ficam no módulo puro [`contests.py`](contests.py), testado em [`tests/`](tests/).

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).