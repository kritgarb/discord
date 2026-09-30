# Feeds → Discord

Automação de Discord em duas partes:

- **Feeds** (`feeds/`): integrações que rodam de hora em hora no GitHub Actions, buscam conteúdo na web e publicam via webhook.
- **Bot de ponto** (`ponto/`): bot que fica no ar numa VPS e contabiliza as horas dos freelas com `/entrar` e `/sair`.

| Feature | O que faz | Spec |
|---|---|---|
| Plataforma de feeds | Fluxo comum: deduplicação, primeira execução, `--dry-run`, `--test`, agendamento | [001](specs/001-plataforma-feeds/spec.md) |
| Missões Sebrae/SE | Missões empresariais com inscrições abertas (Agência + Portal Sebrae), com evento, local, data, valor e prazo | [002](specs/002-missoes-sebrae/spec.md) |
| Compilado do Código Fonte TV | Manchetes de cada edição nova | [003](specs/003-compilado/spec.md) |
| Bot de ponto | Relógio de ponto dos freelas, com relatório e CSV para o admin | [004](specs/004-bot-ponto/spec.md) |

## Spec Driven Development

Este projeto segue **Spec Driven Development**: o comportamento é definido em [`specs/`](specs/) **antes** do código, e cada requisito é ligado ao código e aos testes que o verificam.

- [`specs/README.md`](specs/README.md): o processo, as convenções (requisitos no formato EARS, IDs, status) e o índice.
- [`specs/constitution.md`](specs/constitution.md): princípios que valem para todas as features (não fazer spam, não postar errado, testável sem rede, segredos fora do código…).
- [`specs/_templates/`](specs/_templates/): modelos de `spec.md`, `plan.md` e `tasks.md`.

**Para mudar ou criar algo:** comece pela spec (requisito com ID novo), depois o plano, as tarefas, o código com testes e, por fim, a rastreabilidade. Esse README cobre só **uso e operação**; as regras de cada feature estão nas specs.

## Estrutura

```
specs/                           # especificações (fonte da verdade do comportamento)
feeds/                           # integrações publicadas via webhook (specs 001–003)
├── core/                        # classe base Integration, estado, webhook, HTTP, relógio, config
└── integrations/                # sebrae/ e compilado/
ponto/                           # bot de relógio de ponto (spec 004)
├── service.py                   # regras (TimeClock), sem dependência do Discord
├── repository.py                # SQLite
└── bot/                         # cogs e cliente do Discord
tests/                           # unittest, sem acesso à rede
state/                           # o que cada feed já enviou (commitado pelo workflow)
.github/workflows/feeds.yml      # cron de hora em hora dos feeds
Dockerfile, docker-compose.yml   # deploy do bot na VPS
```

Detalhes de arquitetura e decisões: `plan.md` de cada spec.

## Testes

```bash
python -m unittest discover -s tests -t . -v
```

Os testes não acessam a rede e não dependem do `discord.py`. No Actions, rodam antes da publicação: se falharem, nada é enviado.

---

## Feeds (GitHub Actions)

### Rodando localmente

Requer Python 3.9+.

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha as URLs dos webhooks. O `.env` está no `.gitignore`. No Actions, os valores vêm dos secrets.

```
python -m feeds {missoes,compilado,all} [--dry-run] [--test [N]]
```

| Comando | O que faz |
|---|---|
| `python -m feeds all` | Execução normal (a mesma do cron): posta só o que é novo e atualiza `state/` |
| `python -m feeds missoes` | Só uma integração |
| `python -m feeds all --dry-run` | Mostra o que seria postado, sem enviar nem salvar estado |
| `python -m feeds compilado --test` | Reenvia o item mais recente, sem alterar o estado (para testar o card) |
| `python -m feeds missoes --test 3 --dry-run` | Mostra os campos extraídos das 3 missões mais recentes |

> ⚠️ Se rodar a execução normal localmente, faça commit e push de `state/`. Senão, o Actions não sabe o que já foi enviado e posta de novo.

### Setup

1. Crie um webhook para cada canal: **Configurações do canal → Integrações → Webhooks → Novo webhook → Copiar URL**.
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Canal |
   |---|---|
   | `DISCORD_WEBHOOK_URL` | Missões Sebrae/SE |
   | `DISCORD_WEBHOOK_COMPILADO_URL` | Compilado do Código Fonte TV |

3. Para rodar na hora: **Actions → Feeds → Discord → Run workflow**.

O workflow roda de hora em hora (em UTC): testes → `python -m feeds all` → commit de `state/`, com até 5 tentativas de push.

- **Não apague os arquivos em `state/`**: sem eles, a integração entende que é a primeira execução.
- **Se o job ficar vermelho no passo "Salvar estado"**, não use *Re-run*: marque os itens como enviados no `state/` antes da próxima execução, senão eles são reenviados.
- **O GitHub desativa o cron** em repositórios sem atividade por 60 dias. Se isso acontecer, reative na aba Actions.

---

## Bot de ponto

### Comandos

| Comando | Quem | O que faz |
|---|---|---|
| `/entrar [nota]` | freela | Abre o ponto |
| `/pausa` / `/retomar` | freela | Pausa e retoma; o tempo em pausa não conta |
| `/sair` | freela | Fecha o ponto; mostra a sessão e o total do mês |
| `/status` | freela | Ponto aberto? Quanto já trabalhou hoje? |
| `/horas [periodo]` | freela | Sessões e total no período (padrão: este mês) |
| `/ponto-admin relatorio [periodo] [freela]` | admin | Horas por pessoa + CSV |
| `/ponto-admin ajustar <freela> <duracao> <motivo>` | admin | Soma ou subtrai horas: `1h30`, `45m`, `-0h15` |
| `/ponto-admin fechar <freela> [horario]` | admin | Fecha o ponto de quem esqueceu, no horário informado (`18:30`) |
| `/ponto-admin abertos` | admin | Quem está com o ponto aberto |

As respostas são privadas. Os comandos de admin só aparecem para quem tem **Gerenciar servidor**. As regras completas (períodos, lembrete, sessões na virada do dia) estão na [spec 004](specs/004-bot-ponto/spec.md).

### Criando o bot no Discord

1. [Developer Portal](https://discord.com/developers/applications) → sua aplicação → **Bot**:
   - **Reset Token** e guarde o token (vai no `.env` da VPS; **nunca** no git ou em chat).
   - Desligue **Public Bot**. Nenhum *Privileged Gateway Intent* é necessário.
2. Convide o bot para o servidor:

   ```
   https://discord.com/oauth2/authorize?client_id=1554606589636255845&scope=bot+applications.commands&permissions=0
   ```

3. Ative o **Modo desenvolvedor** (Configurações → Avançado), clique com o botão direito no servidor → **Copiar ID do servidor** e use em `PONTO_GUILD_ID`.

### Deploy na VPS (Docker)

```bash
git clone https://github.com/kritgarb/discord.git && cd discord
cp .env.example .env && chmod 600 .env    # preencha PONTO_BOT_TOKEN e PONTO_GUILD_ID (nano .env)
docker compose up -d --build
docker compose logs -f ponto              # "comandos sincronizados" e "Conectado como ..."
```

- **Atualizar**: `git pull && docker compose up -d --build`.
- **Mudou o `.env`**: `docker compose up -d --force-recreate` (um `restart` não recarrega o arquivo).
- **Dados**: volume `ponto-data` (`/data/ponto.db`), que sobrevive a rebuilds.
- **Backup**: `docker compose cp ponto:/data/ponto.db ./ponto-backup.db`.
- **Sem Docker**: `pip install -r requirements-bot.txt` e `python -m ponto` (banco em `data/ponto.db`).

| Variável | Obrigatória | Descrição |
|---|---|---|
| `PONTO_BOT_TOKEN` | sim | Token do bot |
| `PONTO_GUILD_ID` | recomendada | ID do servidor; sem ele, os comandos podem levar até 1h para aparecer |
| `PONTO_LEMBRETE_HORAS` | não | Horas de ponto aberto até o lembrete por DM (padrão `8`; `0` desliga) |
| `PONTO_LOG_LEVEL` | não | `INFO` (padrão) ou `DEBUG` para diagnóstico |
| `PONTO_DB` | não | Caminho do banco (padrão `data/ponto.db`; no Docker, `/data/ponto.db`) |

### Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `403 Forbidden (50001): Missing Access` ao iniciar | Bot fora do servidor ou `PONTO_GUILD_ID` errado | Convide pelo link acima; confira o ID do **servidor** |
| Comandos não aparecem | Bot removido, ID de outro servidor ou cache do app | Reconvide, confira o `.env` e recrie o container; `Ctrl+R` no Discord |
| Log parado em "logging in" | Rate limit depois de muitas tentativas | `PONTO_LOG_LEVEL=DEBUG` e confira as requisições |
