# Feeds → Discord

Integrações que rodam de hora em hora no GitHub Actions e postam no Discord, cada uma no seu canal (webhook próprio):

| Integração | Fonte | Script | Webhook (variável) |
|---|---|---|---|
| [Missões Sebrae/SE](#missões-sebraese) | Agência Sebrae de Notícias (SE) | `sebrae_missoes.py` | `DISCORD_WEBHOOK_URL` |
| [Compilado do Código Fonte TV](#compilado-do-código-fonte-tv) | compilado.codigofonte.com.br | `compilado.py` | `DISCORD_WEBHOOK_COMPILADO_URL` |

As duas **só postam o que ainda não foi enviado**: cada uma guarda o que já mandou num arquivo de estado (`posted.json` e `posted_compilado.json`).

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

```
feed RSS  ──►  filtra títulos com "missão/missões"  ──►  já enviada? (posted.json)
                                                               │ não
                                                               ▼
               página da notícia  +  edital (PDF)  ──►  extrai os campos  ──►  webhook do Discord
```

1. **Busca**: lê o feed principal `https://se.agenciasebrae.com.br/feed/` (3 páginas ≈ 30 posts por execução; na primeira execução, até 30 páginas).
2. **Filtra**: mantém só posts cujo título contém *missão/missões*.
3. **Deduplica**: ignora o que já está no `posted.json`.
4. **Extrai** os detalhes de cada missão nova:

   | Campo | Fonte |
   |---|---|
   | Evento, local, data | 1º parágrafo da notícia (*"levará empreendedores à X, …, que acontecerá na cidade de Y, no período de Z"*); se faltar, preâmbulo do edital |
   | Valor | item 10.1 do edital (*"O valor a ser pago pelo participante… R$ X"*) |
   | Prazo de inscrição | a **data mais recente** entre: período de inscrição da notícia, prorrogações (*"prorrogado até…"*) e item 8.3 do edital mais novo (erratas) |
   | Edital | último link de PDF com "edital" no post (erratas vêm depois do original) |
   | Inscrição | link `forms.office.com` do post |

5. **Posta** um card por missão, da mais antiga para a mais nova, e registra no `posted.json`.

Campos que não forem encontrados são omitidos do card. Se quase nada for encontrado (ex.: notícia que não segue o modelo padrão), o card mostra o resumo da notícia.

O `posted.json` guarda, para cada missão enviada, o `guid` do RSS (`?p=ID`) **e** o link da notícia. Se qualquer um dos dois já estiver lá, a missão não é enviada de novo.

### Comandos

| Comando | O que faz |
|---|---|
| `python sebrae_missoes.py` | Execução normal (a mesma do cron): posta só as missões novas e atualiza o `posted.json` |
| `python sebrae_missoes.py --dry-run` | Mostra no terminal o que seria postado, sem enviar nada |
| `python sebrae_missoes.py --test 3` | Posta as 3 missões mais recentes **mesmo que já enviadas**, sem alterar o `posted.json`. Para testar o visual do card |
| `python sebrae_missoes.py --test 3 --dry-run` | Mostra no terminal os campos extraídos das 3 mais recentes |

### Configuração

Constantes no topo de [`sebrae_missoes.py`](sebrae_missoes.py):

| Constante | Padrão | Descrição |
|---|---|---|
| `FEED_URL` | `https://se.agenciasebrae.com.br/feed/` | Feed RSS de origem |
| `MISSION_RE` | `missão/missões` | Regex aplicada ao título para identificar missões |
| `PAGES_PER_RUN` | `3` | Páginas do feed lidas em cada execução normal |
| `MAX_PAGES_FIRST_RUN` | `30` | Páginas lidas na primeira execução (sem `posted.json`) ou no `--test` |
| `EMBED_COLOR` | `0x005EB8` | Cor da barra lateral do card |

### Limitações conhecidas

- **Não usamos a busca do site** (`?s=missão`): o índice dela está desatualizado e deixa missões de fora. O feed principal é completo.
- **O conteúdo do RSS pode estar desatualizado** (ex.: sem as prorrogações/erratas mais recentes). Por isso os detalhes são lidos direto da página da notícia.
- **O valor é aproximado**: é o que consta no edital, que avisa que pode mudar na contratação.
- **A extração depende do padrão de texto** das notícias e editais do Sebrae/SE. Se o modelo mudar, algum campo pode deixar de aparecer; o post continua sendo enviado com o que foi encontrado. Use `--test N --dry-run` para conferir.
- Se o edital estiver fora do ar ou não puder ser lido, o card sai sem valor, e o aviso aparece no log.

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

1. **Busca**: o site (plataforma Pingback) não tem RSS. A lista das 12 edições mais recentes vem no JSON embutido na home (`<script id="__NEXT_DATA__">`), com título, data de publicação, banner e slug.
2. **Manchetes**: o texto completo das edições é só para inscritos, mas o título já traz as manchetes: `COMPILADO #263 - manchete 1; manchete 2; …`. O script separa o nome da edição (antes do ` - `) e as manchetes (separadas por `;`).
3. **Seleciona**: posta as edições que ainda não estão no `posted_compilado.json`.
   - **Na primeira execução** (sem o arquivo), todas as edições publicadas **antes de hoje** (horário de Brasília) são marcadas como enviadas. Só a edição do dia, se existir, é postada. Assim o histórico não é despejado no canal.
   - Nas execuções seguintes, qualquer edição nova é postada, inclusive uma publicada perto da meia-noite que só seja vista na execução do dia seguinte.
4. **Posta** um card por edição e registra o `uid` no `posted_compilado.json`.

As edições não saem num dia fixo da semana, e às vezes várias saem juntas. Por isso o script verifica de hora em hora, junto com as missões.

### Comandos

| Comando | O que faz |
|---|---|
| `python compilado.py` | Execução normal (a mesma do cron): posta as edições novas e atualiza o `posted_compilado.json` |
| `python compilado.py --dry-run` | Mostra no terminal o que seria postado, sem enviar nada |
| `python compilado.py --test` | Posta a edição mais recente **mesmo que já enviada**, sem alterar o estado. Para testar o card |
| `python compilado.py --test 3` | Mesma coisa, com as 3 mais recentes |

### Configuração

Constantes no topo de [`compilado.py`](compilado.py): `HOME_URL`, `YOUTUBE_URL`, `SPOTIFY_URL`, `BRT` (fuso usado para "hoje", UTC−3) e `EMBED_COLOR`.

### Limitações conhecidas

- **Depende do JSON interno do site** (`props.pageProps.channelProps.homeData.articles`). Se a plataforma mudar esse formato, o script falha com uma mensagem clara no log em vez de postar algo errado.
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

O workflow [`.github/workflows/missoes.yml`](.github/workflows/missoes.yml) roda de hora em hora (`cron: "0 * * * *"`, em UTC). Ele executa as duas integrações em sequência (se uma falhar, a outra roda mesmo assim) e no fim faz commit dos arquivos de estado.

O GitHub pode atrasar execuções agendadas em alguns minutos e desativa o cron em repositórios sem atividade por 60 dias; nesse caso é só reativar na aba Actions.

**Não apague os arquivos de estado** (`posted.json`, `posted_compilado.json`). Sem eles, o script entende que é a primeira execução.

## Rodando local

Requer Python 3.9+.

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha as URLs dos webhooks. O `.env` está no `.gitignore` e nunca vai para o repositório. No Actions, os valores vêm dos secrets, que têm prioridade sobre o `.env`.

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_COMPILADO_URL=https://discord.com/api/webhooks/...
```

> ⚠️ Se rodar a execução normal (sem `--test`/`--dry-run`) localmente, faça commit e push dos arquivos de estado atualizados. Senão, o Actions não sabe o que já foi enviado e posta de novo.

## Estrutura

```
.
├── sebrae_missoes.py           # integração: missões Sebrae/SE
├── compilado.py                # integração: Compilado do Código Fonte TV
├── common.py                   # utilitários compartilhados (.env, HTTP, estado, webhook)
├── posted.json                 # missões já enviadas (atualizado pelo workflow)
├── posted_compilado.json       # edições do Compilado já enviadas (criado na 1ª execução)
├── requirements.txt            # pypdf (leitura dos editais)
├── .env.example                # modelo de variáveis para rodar local
└── .github/workflows/
    └── missoes.yml             # cron de hora em hora no GitHub Actions
```
