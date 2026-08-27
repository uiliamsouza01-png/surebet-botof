# Bot de Surebets — Scanner automático via Telegram

Este bot varre odds de casas de apostas (via **The Odds API**, uma fonte
agregada e legal de odds — evita scraping direto das casas, que costuma
violar os termos de uso delas) e te avisa no Telegram sempre que encontra
uma arbitragem (surebet) com lucro garantido.

Tudo abaixo pode ser feito pelo celular, sem precisar de computador —
só de um navegador e do Telegram.

## 1. Criar o bot no Telegram (2 min)

1. Abra o Telegram e converse com **@BotFather**.
2. Mande `/newbot`, escolha um nome e um username (precisa terminar em `bot`).
3. Ele te devolve um **token** — algo como `123456789:AAExxxxxxx...`. Guarde.

## 2. Pegar a chave da The Odds API (2 min, plano free)

1. Acesse https://the-odds-api.com e crie uma conta grátis.
2. O plano free dá ~500 requisições/mês — suficiente pra rodar a cada
   10-15 min monitorando alguns esportes.
3. Copie a **API key** que aparece no seu painel.

## 3. Subir o código num repositório (Github, pelo celular)

1. Crie uma conta gratuita no GitHub (app ou navegador).
2. Crie um repositório novo, ex.: `surebet-bot`.
3. Envie os arquivos desta pasta (`main.py`, `requirements.txt`,
   `.env.example`) pra dentro dele — dá pra fazer isso direto no app do
   GitHub ou no site, sem terminal.

## 4. Hospedar rodando 24h (grátis) — Railway

1. Acesse https://railway.app e crie conta (dá pra logar com o GitHub).
2. Clique em **New Project → Deploy from GitHub repo** e selecione o
   `surebet-bot` que você criou.
3. Em **Variables**, adicione as variáveis do `.env.example`:
   - `TELEGRAM_BOT_TOKEN`
   - `ODDS_API_KEY`
   - `SPORTS`, `REGIONS`, `MIN_PROFIT_PERCENT`, `SCAN_INTERVAL_MINUTES`,
     `STAKE_EXAMPLE` (pode deixar os valores padrão do exemplo)
   - `TELEGRAM_CHAT_ID` — deixe em branco por enquanto.
4. O Railway detecta o `requirements.txt` e sobe o bot sozinho.

(Render.com e PythonAnywhere também funcionam de forma parecida, caso
prefira — o código não muda.)

## 5. Pegar seu chat_id e ativar os alertas

1. Com o bot já rodando, abra o Telegram e mande `/start` para o seu bot.
2. Ele responde com o seu `chat_id`.
3. Volte no painel do Railway, cole esse número na variável
   `TELEGRAM_CHAT_ID` e reinicie o serviço (o Railway faz isso sozinho
   ao salvar a variável).
4. Pronto — a partir daí ele te avisa automaticamente sempre que achar
   uma surebet, sem você precisar fazer mais nada.

## Comandos do bot

- `/start` — mostra seu chat_id
- `/status` — mostra a configuração atual (esportes, intervalo, etc.)
- `/scan` — força uma varredura na hora

## Ajustando o que o bot monitora

Tudo é configurável por variável de ambiente, sem mexer no código:

- `SPORTS`: lista de esportes/ligas (veja a lista completa em
  https://the-odds-api.com/sports-odds-data/sports-apis.html)
- `REGIONS`: quais regiões de casas de apostas cobrir (`us`, `uk`, `eu`, `au`)
- `MIN_PROFIT_PERCENT`: a partir de qual % de lucro ele te avisa
- `SCAN_INTERVAL_MINUTES`: de quanto em quanto tempo ele varre (cuidado
  com o limite de requisições do plano free — cada varredura consome 1
  requisição por esporte configurado)

## Avisos importantes

- **Odds mudam rápido.** O bot te avisa, mas confirme o valor exato nas
  casas antes de apostar — a margem de lucro pode fechar em segundos.
- **Limites de conta.** Casas de apostas costumam limitar/restringir
  contas identificadas como "arbers". Isso é uma prática comum do
  mercado, não algo que o bot controla.
- **Mercado h2h apenas.** Esta versão olha só o mercado de
  "resultado final" (moneyline/h2h). Outros mercados (handicap, over/under
  etc.) podem ser adicionados depois se você quiser.
- **Fiscal/legal.** Regras de apostas e tributação variam por país e
  estado — vale se informar sobre a sua situação.
