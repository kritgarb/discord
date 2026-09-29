# Feeds → Discord

Automação de Discord em duas partes:

- **Feeds** (`feeds/`): integrações que rodam de hora em hora no GitHub Actions, buscam conteúdo na web e publicam via webhook.
- **[Bot de ponto](#bot-de-ponto)** (`ponto/`): bot que fica no ar numa VPS e contabiliza as horas dos freelas com `/entrar` e `/sair`.

### Feeds

Cada integração publica no seu canal (webhook próprio):

| Integração | Fonte | Comando | Webhook (variável) |
|---|---|---|---|
| [Missões Sebrae/SE](#missões-sebraese) | Agência Sebrae de Notícias e Portal Sebrae (SE) | `python -m feeds missoes` | `DISCORD_WEBHOOK_URL` |
| [Compilado do Código Fonte TV](#compilado-do-código-fonte-tv) | compilado.codigofonte.com.br | `python -m feeds compilado` | `DISCORD_WEBHOOK_COMPILADO_URL` |

Todas **só postam o que ainda não foi enviado**: cada integração guarda o que já mandou em `state/<integração>.json`.

## Uso

Requer Python 3.9+.

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha as URLs dos webhooks. O `.env` está no `.gitignore` e nunca vai para o repositório. No Actions, os valores vêm dos secrets, que têm prioridade sobre o `.env`.

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_COMPILADO_URL=https://discord.com/api/webhooks/...
```

### Comandos

```
python -m feeds {missoes,compilado,all} [--dry-run] [--test [N]]
```

| Comando | O que faz |
|---|---|
| `python -m feeds all` | Execução normal (a mesma do cron): roda todas as integrações, posta só o que é novo e atualiza o estado |
| `python -m feeds missoes` | Só uma integração |
| `python -m feeds all --dry-run` | Mostra no terminal o que seria postado, sem enviar nem salvar estado |
| `python -m feeds compilado --test` | Envia o item mais recente **mesmo que já enviado**, sem alterar o estado. Para testar o card |
| `python -m feeds missoes --test 3` | Mesma coisa, com os 3 mais recentes |
| `python -m feeds missoes --test 3 --dry-run` | Mostra os campos extraídos dos 3 mais recentes, sem enviar |

No `all`, se uma integração falhar, as outras rodam mesmo assim e o comando termina com código de saída 1.

> ⚠️ Se rodar a execução normal (sem `--test`/`--dry-run`) localmente, faça commit e push da pasta `state/`. Senão, o Actions não sabe o que já foi enviado e posta de novo.

### Testes

```bash
python -m unittest -v
```

Os testes não acessam a rede: cobrem o fluxo da classe base (deduplicação, primeira execução, `--test`, `--dry-run`) e a extração de campos com textos reais dos sites. No Actions, os testes rodam antes da publicação; se falharem, nada é enviado.

---

## Arquitetura

```
feeds/
├── __main__.py                  # CLI: python -m feeds ...
├── core/                        # infraestrutura comum
│   ├── integration.py           # Integration: classe base abstrata com o fluxo completo
│   ├── discord.py               # DiscordWebhook: envio de embeds + tratamento de rate limit
│   ├── state.py                 # SeenStore: registro do que já foi enviado (JSON)
│   ├── http.py                  # HttpClient: GET/POST sobre a biblioteca padrão
│   ├── clock.py                 # "hoje" no horário de Brasília
│   └── config.py                # .env, variáveis obrigatórias, ConfigError
└── integrations/
    ├── __init__.py              # INTEGRATIONS: registro slug → classe
    ├── sebrae/
    │   ├── integration.py       # SebraeMissoes(Integration)
    │   ├── source.py            # SebraeFeed (Agência, RSS), SebraePortal (sitemap + .model.json)
│   │                        # e MissionExtractor (página + edital PDF)
    │   ├── parsing.py           # funções puras de extração de texto
    │   └── models.py            # Mission (dataclass)
    └── compilado/
        ├── integration.py       # Compilado(Integration)
        ├── source.py            # CompiladoSite + parse_home (JSON __NEXT_DATA__)
        └── models.py            # Edition (dataclass)
ponto/                           # bot de relógio de ponto (ver "Bot de ponto")
tests/                           # unittest, sem acesso à rede
state/                           # o que já foi enviado, por integração (commitado pelo workflow)
.github/workflows/feeds.yml      # cron de hora em hora
Dockerfile, docker-compose.yml   # deploy do bot de ponto na VPS
```

### Fluxo da classe base

`Integration.run()` faz o mesmo para todas as integrações:

```
fetch()  ──►  já enviado? (SeenStore + keys())  ──►  enrich()  ──►  skip_reason()?  ──►  to_embed()  ──►  DiscordWebhook
                    ▲                                                                      │
                    └──────────────────────── state.save() ◄───────────────────────────────┘
```

1. **`fetch(full, limit)`**: busca os itens, do mais antigo para o mais novo. `full=True` pede uma busca mais profunda (primeira execução ou `--test`).
2. **Filtra** os itens cujas **`keys()`** já estão no estado. Na primeira execução, os itens devolvidos por **`bootstrap()`** são marcados como enviados sem postar.
3. **`enrich(item)`**: busca detalhes. Só roda para os itens novos.
4. **`skip_reason(item)`**: se devolver um motivo, o item não é postado, mas é marcado como visto para não ser reavaliado a cada execução (ex.: missão com inscrições encerradas). Não se aplica no `--test`.
5. **`to_embed(item)`**: monta o card, que é enviado pelo `DiscordWebhook`.
6. **Salva o estado**, mesmo se o envio falhar no meio, para não repetir o que já foi.

### Adicionando uma integração

1. Crie `feeds/integrations/<nome>/` com uma subclasse de `Integration`:

   ```python
   class MinhaIntegracao(Integration[MeuItem]):
       slug = "minha"                         # nome na CLI e em state/minha.json
       title = "Minha integração"             # nome nos logs
       username = "Nome no Discord"
       webhook_env = "DISCORD_WEBHOOK_MINHA_URL"

       def fetch(self, *, full, limit): ...   # lista de itens, do mais antigo ao mais novo
       def keys(self, item): ...              # IDs únicos do item
       def label(self, item): ...             # texto curto para logs
       def to_embed(self, item): ...          # embed do Discord
       def summary(self, item): ...           # linhas do --dry-run
       # opcionais: enrich(item), bootstrap(items), skip_reason(item)
   ```

2. Registre a classe em `feeds/integrations/__init__.py` (`INTEGRATIONS`).
3. Adicione a variável no `.env.example`, o secret no GitHub e o `env:` no passo "Publicar no Discord" do workflow.

---

## Missões Sebrae/SE

Acompanha as **missões empresariais do Sebrae/SE** e posta cada missão nova **com inscrições abertas**. As missões saem em dois lugares, e a integração lê os dois:

- [Agência Sebrae de Notícias (SE)](https://se.agenciasebrae.com.br/): notícias, com feed RSS;
- [Portal Sebrae](https://sebrae.com.br/se): páginas em `sebrae.com.br/se/subsites/…`, sem RSS. Hoje a maioria das missões sai só aqui.

Cada card traz as informações principais:

| Campo | Exemplo |
|---|---|
| 🎯 Evento | Deep Tech Summit 2026 |
| 📍 Local | São Paulo/SP |
| 📅 Data | 11 a 12 de agosto de 2026 |
| 💰 Valor (participante) | ≈ R$ 2.500,00 |
| ⏰ Inscrições até | 30/06/2026 |

O card também traz links para a notícia/página, o edital e o formulário de inscrição.

### Como funciona

1. **Busca** nas duas fontes:
   - **Agência** (`SebraeFeed`): feed principal `https://se.agenciasebrae.com.br/feed/`, com 3 páginas (≈ 30 posts) por execução e até 30 na primeira execução.
   - **Portal** (`SebraePortal`): lê o `sitemap.xml` do portal, pega as páginas `sebrae.com.br/se/subsites/…` com *miss* na URL e baixa o `.model.json` de cada uma (conteúdo estruturado do Adobe AEM). Páginas já vistas não são baixadas de novo.
2. **Filtra**: mantém só itens cujo título contém *missão/missões*.
3. **Deduplica** pelo `guid`, pelo link **e** pelo título normalizado (sem acento, pontuação e caixa). Se qualquer um já estiver no estado, a missão não é reenviada, mesmo que apareça na outra fonte.
4. **Extrai** os detalhes (`MissionExtractor`):

   | Campo | Fonte |
   |---|---|
   | Evento, local, data | 1º parágrafo do texto (*"levará empreendedores à X, …"* na Agência, *"Missão … destinada ao X, …"* no Portal, seguido de *"que acontecerá na cidade de Y, no período de Z"*); se faltar, preâmbulo do edital |
   | Valor | item 10.1 do edital (*"O valor a ser pago pelo participante… R$ X"*) |
   | Prazo de inscrição | a **data mais recente** entre: período de inscrição do texto, descrição (*"inscreva-se até…"*), prorrogações (*"prorrogado até…"*) e item 8.3 do edital mais novo (erratas) |
   | Edital | último link de PDF com "edital" no post (erratas vêm depois do original) |
   | Inscrição | link de formulário (`forms.office.com`, `forms.cloud.microsoft`) |

5. **Ignora missões com inscrições encerradas** (prazo anterior a hoje, no horário de Brasília): elas são marcadas como vistas sem postar. Missão sem prazo identificado é postada.
6. **Posta** um card por missão aberta, da mais antiga para a mais nova.

Campos que não forem encontrados são omitidos. Se quase nada for encontrado (ex.: notícia fora do modelo padrão), o card mostra o resumo da notícia.

### Limitações conhecidas

- **A Agência não publica todas as missões.** Em setembro/2026, das 9 missões do Sebrae/SE no Portal, só 1 tinha saído na Agência. Por isso o Portal é a fonte principal.
- **O Portal não tem data de publicação**: usamos a data da última modificação da página (`lastModifiedDate`).
- **Não usamos a busca da Agência** (`?s=missão`): o índice dela está desatualizado e deixa missões de fora. O feed principal é completo.
- **O conteúdo do RSS pode estar desatualizado** (ex.: sem as prorrogações/erratas mais recentes). Por isso os detalhes são lidos direto da página da notícia.
- **O valor é aproximado**: é o que consta no edital, que avisa que pode mudar na contratação.
- **A extração depende do padrão de texto** das páginas e editais do Sebrae/SE, e reproduz erros do site (ex.: a página da Fenalaw 2026 diz "São Paulo (PE)"). Se o modelo mudar, algum campo pode deixar de aparecer, e o post é enviado com o que foi encontrado. Use `--test N --dry-run` para conferir.
- Se o edital estiver fora do ar ou ilegível, o card sai sem valor, e o aviso aparece no log.

---

## Compilado do Código Fonte TV

Posta a edição do dia do [Compilado do Código Fonte TV](https://compilado.codigofonte.com.br/), com as principais notícias da semana do mundo da programação:

```
COMPILADO #263
• Líderes tech divergem sobre frear IA
• CEO da Automattic de volta
• Agentes da OpenAI invadem RubyGems
• Novos Java 27 e Swift 6.4

Ler edição · YouTube · Spotify
[banner da edição]
```

### Como funciona

1. **Busca**: o site (plataforma Pingback) não tem RSS. As 12 edições mais recentes vêm no JSON embutido na home (`<script id="__NEXT_DATA__">`), com título, data de publicação, banner e slug.
2. **Manchetes**: o texto das edições é só para inscritos, mas o título já traz as manchetes: `COMPILADO #263 - manchete 1; manchete 2; …`.
3. **Seleciona** as edições que ainda não estão no estado (deduplica pelo `uid`).
   - **Na primeira execução**, as edições publicadas **antes de hoje** (horário de Brasília) são marcadas como enviadas. Só a do dia, se existir, é postada.
   - Nas execuções seguintes, qualquer edição nova é postada, inclusive uma publicada perto da meia-noite que só seja vista na execução seguinte.

As edições não saem num dia fixo da semana, e às vezes várias saem juntas. Por isso o script verifica de hora em hora.

### Limitações conhecidas

- **Depende do JSON interno do site** (`props.pageProps.channelProps.homeData.articles`). Se a plataforma mudar esse formato, a integração falha com uma mensagem clara no log, em vez de postar algo errado.
- **Só as manchetes**: o conteúdo completo é exclusivo para inscritos e não é acessado.
- O número no título (`#263`) e o slug do link (`ep264`) não batem. É assim no próprio site, e o link aponta para a edição certa.

---

## Bot de ponto

Bot do Discord que funciona como relógio de ponto para os freelas: cada um abre e fecha o próprio ponto, e o bot soma as horas. As respostas dos freelas são **privadas** (só quem usou o comando vê). Os comandos de admin só aparecem para quem tem a permissão **Gerenciar servidor**.

### Comandos

| Comando | Quem | O que faz |
|---|---|---|
| `/entrar [nota]` | freela | Abre o ponto (a nota é opcional: no que vai trabalhar) |
| `/pausa` | freela | Pausa o ponto; o tempo em pausa não conta |
| `/retomar` | freela | Volta da pausa |
| `/sair` | freela | Fecha o ponto e mostra o tempo da sessão e o total do mês |
| `/status` | freela | Mostra se o ponto está aberto e quanto já trabalhou |
| `/horas [periodo]` | freela | Suas sessões e o total no período (padrão: este mês) |
| `/ponto-admin relatorio [periodo] [freela]` | admin | Horas por pessoa no período + **CSV** (abre no Excel/Sheets) |
| `/ponto-admin ajustar <freela> <duracao> <motivo>` | admin | Soma ou subtrai horas: `1h30`, `45m`, `-0h15` |
| `/ponto-admin fechar <freela> [horario]` | admin | Fecha o ponto de quem esqueceu, no horário informado (`18:30`) |
| `/ponto-admin abertos` | admin | Quem está com o ponto aberto agora |

Períodos: hoje, esta semana, semana passada, este mês e mês passado (semanas começam na segunda; horário de Brasília).

### Regras

- Cada pessoa tem no máximo **um ponto aberto** por servidor.
- Uma sessão conta no período **em que começou** (entrou 23:00 do dia 30 e saiu 01:00 do dia 1º: conta no dia 30).
- Só sessões **encerradas** entram nos totais; ajustes entram pela data em que foram feitos.
- **Lembrete**: quem fica com o ponto aberto mais de `PONTO_LEMBRETE_HORAS` (padrão 8h) de trabalho recebe **uma** DM lembrando de sair. Se já tiver passado da hora, um admin fecha com `/ponto-admin fechar` no horário certo.

### Arquitetura

```
ponto/
├── __main__.py        # python -m ponto
├── config.py          # Settings (variáveis de ambiente / .env)
├── models.py          # Session, Adjustment, UserTotal (dataclasses)
├── repository.py      # SQLiteRepository: persistência (SQLite)
├── service.py         # TimeClock: regras do ponto; não depende do Discord
├── timeutil.py        # períodos, durações (1h30) e horários (18:30)
└── bot/
    ├── client.py      # PontoBot: registra os comandos e roda o lembrete (a cada 10 min)
    ├── freela.py      # FreelaCog: /entrar, /pausa, /retomar, /sair, /status, /horas
    ├── admin.py       # AdminCog: /ponto-admin ...
    └── ui.py          # escolhas de período e tratamento de erros
```

As regras ficam no `TimeClock`, que recebe o repositório e um relógio injetáveis. Os testes (`tests/test_ponto.py`) usam SQLite em memória e um relógio falso, sem Discord.

### Criando o bot no Discord

1. [Developer Portal](https://discord.com/developers/applications) → sua aplicação → **Bot**:
   - **Reset Token** e guarde o token (vai no `.env` da VPS; **nunca** no git ou em chat).
   - Desligue **Public Bot**, para só você poder adicioná-lo a servidores.
   - Nenhum *Privileged Gateway Intent* é necessário.
2. Convide o bot para o servidor com este link (troque o `client_id` se usar outra aplicação):

   ```
   https://discord.com/oauth2/authorize?client_id=1554606589636255845&scope=bot+applications.commands&permissions=0
   ```

   `permissions=0` porque o bot só responde a comandos e manda DMs.
3. Copie o ID do servidor (Configurações → Avançado → **Modo desenvolvedor**; depois clique com o botão direito no servidor → **Copiar ID**) para `PONTO_GUILD_ID`. Com ele, os comandos aparecem na hora.

### Deploy na VPS (Docker)

Na VPS, com Docker e o plugin Compose instalados:

```bash
git clone https://github.com/kritgarb/discord.git && cd discord
cp .env.example .env    # preencha PONTO_BOT_TOKEN e PONTO_GUILD_ID
docker compose up -d --build
docker compose logs -f ponto    # deve aparecer "comandos sincronizados" e "Conectado como ..."
```

- **Atualizar**: `git pull && docker compose up -d --build`.
- **Dados**: o banco fica no volume `ponto-data` (`/data/ponto.db` dentro do container) e sobrevive a rebuilds.
- **Backup**: `docker compose cp ponto:/data/ponto.db ./ponto-backup.db`.

Para rodar sem Docker: `pip install -r requirements-bot.txt` e `python -m ponto` (o banco fica em `data/ponto.db`).

| Variável | Obrigatória | Descrição |
|---|---|---|
| `PONTO_BOT_TOKEN` | sim | Token do bot |
| `PONTO_GUILD_ID` | recomendada | ID do servidor: os comandos aparecem na hora. Sem ela, a sincronização global pode levar até 1h |
| `PONTO_LEMBRETE_HORAS` | não | Horas de ponto aberto até o lembrete por DM (padrão `8`; `0` desliga) |
| `PONTO_DB` | não | Caminho do banco SQLite (padrão `data/ponto.db`; no Docker, `/data/ponto.db`) |

---

## Setup dos feeds (GitHub Actions)

1. Crie um webhook para cada canal no Discord: **Configurações do canal → Integrações → Webhooks → Novo webhook → Copiar URL**.
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**, um para cada:

   | Secret | Canal |
   |---|---|
   | `DISCORD_WEBHOOK_URL` | Missões Sebrae/SE |
   | `DISCORD_WEBHOOK_COMPILADO_URL` | Compilado do Código Fonte TV |

3. Se quiser rodar na hora: **Actions → Feeds → Discord → Run workflow**.

O workflow [`.github/workflows/feeds.yml`](.github/workflows/feeds.yml) roda de hora em hora (`cron: "0 * * * *"`, em UTC): instala as dependências, roda os testes, executa `python -m feeds all` e faz commit da pasta `state/`. O push do estado tenta até 5 vezes (com `pull --rebase` antes de cada uma), porque, se ele não subir, a execução seguinte reenvia as mensagens. Se as 5 falharem, o job fica vermelho com um aviso; nesse caso, marque os itens como enviados antes da próxima execução.

O GitHub pode atrasar execuções agendadas em alguns minutos e desativa o cron em repositórios sem atividade por 60 dias; nesse caso é só reativar na aba Actions.

**Não apague os arquivos em `state/`.** Sem eles, a integração entende que é a primeira execução.
