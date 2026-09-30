# Constituição do projeto

Princípios que valem para **todas** as features. Um plano (`plan.md`) que viole algum princípio precisa justificar a exceção na seção **Verificação da constituição**.

## Princípios

### C1. Não fazer spam no canal
Um item publicado **nunca** é publicado de novo automaticamente, e o histórico **nunca** é despejado de uma vez num canal. Toda integração é idempotente: rodar duas vezes seguidas não gera mensagens repetidas.

### C2. Melhor não postar do que postar errado
Se a fonte mudou de formato a ponto de a leitura ficar incerta, a integração **falha com uma mensagem clara no log**, em vez de publicar algo incorreto. Campos opcionais que não puderem ser extraídos são **omitidos**, nunca inventados.

### C3. Regras testáveis sem rede
Regras de negócio ficam em funções puras ou em classes com dependências injetáveis (HTTP, relógio, repositório). A suíte de testes **não acessa a rede** e roda no CI antes de qualquer publicação. Se os testes falharem, nada é publicado.

### C4. Segredos fora do código
Tokens e URLs de webhook vivem **só** em variáveis de ambiente: `.env` local (no `.gitignore`), secrets do GitHub ou `.env` da VPS. Nunca no git, em logs ou em mensagens de chat.

### C5. Horário de Brasília é a referência
"Hoje", "esta semana" e prazos são calculados em **UTC−3** (Brasília, sem horário de verão), via `feeds/core/clock.py`. Datas são armazenadas com fuso (UTC).

### C6. Dependências mínimas e isoladas
Biblioteca padrão primeiro. Cada componente instala só o que usa: os feeds dependem de `pypdf` (`requirements.txt`) e o bot, de `discord.py` (`requirements-bot.txt`). Um componente não pode quebrar por causa da dependência de outro.

### C7. Privacidade por padrão no bot
Respostas a comandos de usuários são **privadas** (efêmeras). Dados de uma pessoa só são visíveis a ela e aos admins. Mensagens automáticas **não mencionam** ninguém.

### C8. Rastreabilidade
Todo requisito tem um ID, e toda spec implementada tem uma tabela ligando cada requisito ao código e ao teste (ou à verificação manual).

### C9. Documentação em pt-BR
Specs, planos, mensagens para o usuário e comentários de código são escritos em português do Brasil. Identificadores de código podem ficar em inglês.

## Governança

- Esta constituição muda por alteração explícita neste arquivo, registrada no histórico abaixo.
- Em caso de conflito entre uma spec e a constituição, a constituição vence até que uma das duas seja alterada.

## Histórico

| Data | Mudança |
|---|---|
| 2026-09-30 | Versão inicial, extraída das decisões já tomadas nas features 001–004 |
