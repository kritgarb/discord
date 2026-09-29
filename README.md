# Feeds → Discord

Integrações que rodam de hora em hora no GitHub Actions, buscam conteúdo na web e publicam no Discord, cada uma no seu canal (webhook próprio):

| Integração | Fonte | Comando | Webhook (variável) |
|---|---|---|---|
| [Missões Sebrae/SE](#missões-sebraese) | Agência Sebrae de Notícias (SE) | `python -m feeds missoes` | `DISCORD_WEBHOOK_URL` |
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
│   └── config.py                # .env, variáveis obrigatórias, ConfigError
└── integrations/
    ├── __init__.py              # INTEGRATIONS: registro slug → classe
    ├── sebrae/
    │   ├── integration.py       # SebraeMissoes(Integration)
    │   ├── source.py            # SebraeFeed (RSS) e MissionExtractor (página + edital PDF)
    │   ├── parsing.py           # funções puras de extração de texto
    │   └── models.py            # Mission (dataclass)
    └── compilado/
        ├── integration.py       # Compilado(Integration)
        ├── source.py            # CompiladoSite + parse_home (JSON __NEXT_DATA__)
        └── models.py            # Edition (dataclass)
tests/                           # unittest, sem acesso à rede
state/                           # o que já foi enviado, por integração (commitado pelo workflow)
.github/workflows/feeds.yml      # cron de hora em hora
```

### Fluxo da classe base

`Integration.run()` faz o mesmo para todas as integrações:

```
fetch()  ──►  já enviado? (SeenStore + keys())  ──►  enrich()  ──►  to_embed()  ──►  DiscordWebhook
                    ▲                                                                      │
                    └──────────────────────── state.save() ◄───────────────────────────────┘
```

1. **`fetch(full, limit)`**: busca os itens, do mais antigo para o mais novo. `full=True` pede uma busca mais profunda (primeira execução ou `--test`).
2. **Filtra** os itens cujas **`keys()`** já estão no estado. Na primeira execução, os itens devolvidos por **`bootstrap()`** são marcados como enviados sem postar.
3. **`enrich(item)`**: busca detalhes. Só roda para os itens que vão ser enviados.
4. **`to_embed(item)`**: monta o card, que é enviado pelo `DiscordWebhook`.
5. **Salva o estado**, mesmo se o envio falhar no meio, para não repetir o que já foi.

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
       # opcionais: enrich(item), bootstrap(items)
   ```

2. Registre a classe em `feeds/integrations/__init__.py` (`INTEGRATIONS`).
3. Adicione a variável no `.env.example`, o secret no GitHub e o `env:` no passo "Publicar no Discord" do workflow.

---

## Missões Sebrae/SE

Acompanha as **missões empresariais** publicadas na [Agência Sebrae de Notícias (SE)](https://se.agenciasebrae.com.br/) e posta cada missão nova com as informações principais:

| Campo | Exemplo |
|---|---|
| 🎯 Evento | Deep Tech Summit 2026 |
| 📍 Local | São Paulo/SP |
| 📅 Data | 11 a 12 de agosto de 2026 |
| 💰 Valor (participante) | ≈ R$ 2.500,00 |
| ⏰ Inscrições até | 30/06/2026 |

O card também traz links para a notícia, o edital e o formulário de inscrição.

### Como funciona

1. **Busca**: o `SebraeFeed` lê o feed principal `https://se.agenciasebrae.com.br/feed/`, com 3 páginas (≈ 30 posts) por execução e até 30 páginas na primeira execução.
2. **Filtra**: mantém só posts cujo título contém *missão/missões*.
3. **Deduplica** pelo `guid` do RSS (`?p=ID`) **e** pelo link: se qualquer um já estiver no estado, a missão não é reenviada.
4. **Extrai** os detalhes (`MissionExtractor`):

   | Campo | Fonte |
   |---|---|
   | Evento, local, data | 1º parágrafo da notícia (*"levará empreendedores à X, …, que acontecerá na cidade de Y, no período de Z"*); se faltar, preâmbulo do edital |
   | Valor | item 10.1 do edital (*"O valor a ser pago pelo participante… R$ X"*) |
   | Prazo de inscrição | a **data mais recente** entre: período de inscrição da notícia, prorrogações (*"prorrogado até…"*) e item 8.3 do edital mais novo (erratas) |
   | Edital | último link de PDF com "edital" no post (erratas vêm depois do original) |
   | Inscrição | link `forms.office.com` do post |

5. **Posta** um card por missão, da mais antiga para a mais nova. Na primeira execução, posta todas as missões existentes.

Campos que não forem encontrados são omitidos. Se quase nada for encontrado (ex.: notícia fora do modelo padrão), o card mostra o resumo da notícia.

### Limitações conhecidas

- **Não usamos a busca do site** (`?s=missão`): o índice dela está desatualizado e deixa missões de fora. O feed principal é completo.
- **O conteúdo do RSS pode estar desatualizado** (ex.: sem as prorrogações/erratas mais recentes). Por isso os detalhes são lidos direto da página da notícia.
- **O valor é aproximado**: é o que consta no edital, que avisa que pode mudar na contratação.
- **A extração depende do padrão de texto** das notícias e editais do Sebrae/SE. Se o modelo mudar, algum campo pode deixar de aparecer, e o post é enviado com o que foi encontrado. Use `--test N --dry-run` para conferir.
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

## Setup (GitHub Actions)

1. Crie um webhook para cada canal no Discord: **Configurações do canal → Integrações → Webhooks → Novo webhook → Copiar URL**.
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**, um para cada:

   | Secret | Canal |
   |---|---|
   | `DISCORD_WEBHOOK_URL` | Missões Sebrae/SE |
   | `DISCORD_WEBHOOK_COMPILADO_URL` | Compilado do Código Fonte TV |

3. Se quiser rodar na hora: **Actions → Feeds → Discord → Run workflow**.

O workflow [`.github/workflows/feeds.yml`](.github/workflows/feeds.yml) roda de hora em hora (`cron: "0 * * * *"`, em UTC): instala as dependências, roda os testes, executa `python -m feeds all` e faz commit da pasta `state/`.

O GitHub pode atrasar execuções agendadas em alguns minutos e desativa o cron em repositórios sem atividade por 60 dias; nesse caso é só reativar na aba Actions.

**Não apague os arquivos em `state/`.** Sem eles, a integração entende que é a primeira execução.
