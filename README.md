# Missões Sebrae/SE → Discord

Busca missões empresariais no RSS da [Agência Sebrae de Notícias (SE)](https://se.agenciasebrae.com.br/feed/) (filtrando pelo título), lê a página da notícia e o edital em PDF e posta no Discord um card com: evento/tipo, local, data, valor para o participante e prazo de inscrição.

Roda de hora em hora no GitHub Actions (`.github/workflows/missoes.yml`). O arquivo `posted.json` guarda o que já foi postado e é commitado pelo próprio workflow.

## Setup

1. No repositório: **Settings → Secrets and variables → Actions → New repository secret**
   - Nome: `DISCORD_WEBHOOK_URL`
   - Valor: a URL do webhook do canal
2. **Actions → Missões Sebrae/SE → Discord → Run workflow** para a primeira execução.

## Rodando local

Copie `.env.example` para `.env` e preencha `DISCORD_WEBHOOK_URL` (o `.env` não vai pro git). No Actions o valor vem do secret.

```bash
pip install -r requirements.txt
```

Só mostrar no terminal o que seria postado:

```bash
python sebrae_missoes.py --dry-run
```

Testar postando as 3 mais recentes (ignora e não altera o `posted.json`):

```bash
python sebrae_missoes.py --test 3
```

```bash
python sebrae_missoes.py
```

Requer Python 3.9+ e `pypdf` (para ler os editais).
