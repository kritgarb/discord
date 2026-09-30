# 004. Bot de ponto dos freelas: Plano técnico

| | |
|---|---|
| **Spec** | [spec.md](spec.md) |

## Visão geral

Um bot `discord.py` que usa só slash commands e roda 24h num container Docker na VPS. As regras ficam num serviço sem dependência do Discord (`TimeClock`), sobre um repositório SQLite. A camada do Discord só traduz comandos em chamadas ao serviço e formata as respostas.

```
Discord (slash command)
   │
   ▼
FreelaCog / AdminCog  ──►  TimeClock (regras)  ──►  SQLiteRepository  ──►  ponto.db (volume Docker)
   │  erros → reply_error         ▲
   ▼                              │ relógio injetável (testes)
resposta efêmera            PontoBot.remind_open_sessions (a cada 10 min) → DM
```

## Componentes

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| `Settings` | Configuração por env/.env | `ponto/config.py` |
| `Session`, `Adjustment`, `UserTotal` | Modelos; `Session.worked_seconds` desconta as pausas | `ponto/models.py` |
| `SQLiteRepository` | Esquema, CRUD, consultas por período | `ponto/repository.py` |
| `TimeClock` | Regras: entrar, pausar, retomar, sair, totais, ajustes, lembretes | `ponto/service.py` |
| `timeutil` | Períodos, `1h30` ↔ segundos, `HH:MM`, formatação | `ponto/timeutil.py` |
| `PontoBot` | Registro de cogs, sincronização dos comandos, laço de lembrete, nomes para o relatório | `ponto/bot/client.py` |
| `FreelaCog` | `/entrar`, `/pausa`, `/retomar`, `/sair`, `/status`, `/horas` | `ponto/bot/freela.py` |
| `AdminCog` | `/ponto-admin relatorio`, `ajustar`, `fechar`, `abertos`, CSV | `ponto/bot/admin.py` |
| `ui` | Escolhas de período, cor e `reply_error` | `ponto/bot/ui.py` |
| Entrada | Logging, tratamento de `SetupError`/`LoginFailure` | `ponto/__main__.py` |
| Deploy | Imagem, volume e reinício automático | `Dockerfile`, `docker-compose.yml` |

## Modelo de dados

SQLite; datas como timestamp Unix (UTC).

- **`sessions`**: `id`, `guild_id`, `user_id`, `started_at`, `ended_at` (nulo = aberta), `paused_at` (nulo = não pausada), `paused_seconds` (pausas encerradas), `note`, `reminded`.
  - Índice único parcial `one_open_session (guild_id, user_id) WHERE ended_at IS NULL`: o banco garante no máximo um ponto aberto (PNT-02).
- **`adjustments`**: `id`, `guild_id`, `user_id`, `seconds` (com sinal), `reason`, `created_by`, `created_at`.

## Decisões

| # | Decisão | Alternativas descartadas | Motivo |
|---|---|---|---|
| D1 | Bot com conexão ao gateway (`discord.py`) em container | Endpoint HTTP de interações (serverless); GitHub Actions | Precisa responder na hora e mandar lembretes; o dono já tem VPS. A chave pública da aplicação não é usada. |
| D2 | SQLite em volume Docker nomeado | Postgres; JSON | Um servidor, pouco volume, zero administração. O volume nomeado herda as permissões da imagem (o container roda sem root). |
| D3 | Regras no `TimeClock`, com repositório e relógio injetáveis | Lógica dentro dos cogs | Constituição C3: as regras são testadas sem Discord, com SQLite em memória e relógio falso. |
| D4 | Pausa como `paused_at` + `paused_seconds` na sessão | Tabela de pausas | O relatório só precisa do tempo líquido; menos consultas e menos estado. |
| D5 | Sessão conta pela data de entrada | Ratear entre dias | Simples de explicar e de conferir; o caso da meia-noite é raro. |
| D6 | Correção por ajuste, e não por edição de sessão | Editar ou excluir sessões | Mantém o histórico auditável: o ajuste tem motivo e autor. |
| D7 | Comandos sincronizados por servidor (`PONTO_GUILD_ID`) | Sincronização global | Aparecem na hora; a global pode levar até 1h. |
| D8 | Tratamento de erro com `cog_app_command_error` | Decorator em cada comando | Mecanismo nativo do `discord.py`; um decorator atrapalharia a leitura da assinatura dos comandos. |
| D9 | `@guild_only` em cada comando de freela | Na classe do cog | Em `Cog` comum, o decorator de classe não se aplica aos comandos (só em `GroupCog`). |
| D10 | Nenhum intent privilegiado; nomes via `fetch_user` | Intent de membros | Menos permissões no portal; nomes só são necessários no relatório. |
| D11 | `ponto/bot/__init__.py` não importa `discord.py` | Reexportar `PontoBot` | Ferramentas que varrem o projeto (ex.: `unittest discover`) não quebram no CI dos feeds, que não instala `discord.py` (C6). |

## Verificação da constituição

| Princípio | Como é atendido |
|---|---|
| C1 Não fazer spam | Só um lembrete por sessão (PNT-14); nenhuma mensagem em canal |
| C2 Não postar errado | Entradas inválidas são recusadas com explicação (PNT-09, PNT-10) |
| C3 Testável sem rede | `tests/test_ponto.py` com SQLite em memória e `FakeNow` |
| C4 Segredos | `PONTO_BOT_TOKEN` só no `.env` da VPS (`chmod 600`); `.dockerignore` exclui o `.env` da imagem |
| C5 Horário de Brasília | `timeutil` e `clock` usam `BRT` |
| C6 Dependências | `requirements-bot.txt` separado; a imagem Docker instala só isso |
| C7 Privacidade | Respostas efêmeras; admin por permissão; `AllowedMentions.none()` nas respostas de admin |

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Freela esquece o ponto aberto | Horas infladas | Lembrete por DM (PNT-14); `/ponto-admin fechar` com horário |
| Perda do volume ou da VPS | Perda do histórico | Backup com `docker compose cp` (questão em aberto: automatizar) |
| Bot fora do servidor ou ID errado | Comandos não aparecem | Mensagem acionável na inicialização (PNT-17) |
| Token vazado | Controle do bot por terceiros | Reset no portal; token só no `.env` da VPS |

## Estratégia de teste

- **Unitário** (`tests/test_ponto.py`): todas as regras do `TimeClock` e do `timeutil`, com relógio controlado.
- **Fumaça**: executar os callbacks dos cogs com interações simuladas (`unittest.mock`) e montar a árvore de comandos offline, para conferir `contexts`/`default_member_permissions`. Foi feito na implementação, mas não está automatizado (questão em aberto).
- **Manual**: roteiro na spec.

## Configuração e deploy

Ver [README › Bot de ponto](../../README.md#bot-de-ponto).
