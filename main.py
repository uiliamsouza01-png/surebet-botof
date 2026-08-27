"""
Bot de Telegram - Scanner automático de Surebets
--------------------------------------------------
Varre odds de vários mercados de apostas esportivas (via The Odds API,
fonte legal e agregada de odds) e avisa no Telegram sempre que encontra
uma arbitragem (surebet) com lucro garantido acima do mínimo configurado.

Não precisa do seu PC ligado: depois de configurado, roda 24h em uma
hospedagem gratuita (veja README.md para o passo a passo).
"""

import os
import asyncio
import logging
from datetime import datetime, timezone

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Configuração (tudo vem de variáveis de ambiente - veja .env.example)
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ODDS_API_KEY = os.environ["ODDS_API_KEY"]

# Chat que vai receber os alertas. Se não souber o seu, rode o bot,
# mande /start e ele te devolve o chat_id certo pra colocar aqui.
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Esportes monitorados (chaves da The Odds API), separados por vírgula.
# Lista completa em: https://the-odds-api.com/sports-odds-data/sports-apis.html
SPORTS = os.environ.get(
    "SPORTS",
    "soccer_brazil_campeonato,soccer_epl,basketball_nba"
).split(",")

# Regiões de casas de apostas cobertas pela API: us, uk, eu, au
REGIONS = os.environ.get("REGIONS", "eu,uk")

# Lucro mínimo (%) para considerar e alertar uma surebet
MIN_PROFIT_PERCENT = float(os.environ.get("MIN_PROFIT_PERCENT", "1.0"))

# Intervalo entre varreduras, em minutos
SCAN_INTERVAL_MINUTES = int(os.environ.get("SCAN_INTERVAL_MINUTES", "10"))

# Valor total hipotético usado para mostrar a divisão de stake no alerta
STAKE_EXAMPLE = float(os.environ.get("STAKE_EXAMPLE", "1000"))

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("surebet-bot")

# Guarda eventos já alertados nesta execução, pra não repetir aviso toda hora
_already_alerted = set()


# ---------------------------------------------------------------------------
# Lógica de arbitragem
# ---------------------------------------------------------------------------

def find_best_odds_per_outcome(bookmakers, market_key="h2h"):
    """
    Recebe a lista de bookmakers de um evento (formato The Odds API) e
    retorna, para cada resultado possível (outcome), a melhor odd
    disponível e em qual casa está.

    Retorna: { outcome_name: {"price": float, "bookmaker": str} }
    """
    best = {}
    for bm in bookmakers:
        for market in bm.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                name = outcome["name"]
                price = outcome["price"]
                if name not in best or price > best[name]["price"]:
                    best[name] = {"price": price, "bookmaker": bm["title"]}
    return best


def calculate_arbitrage(best_odds: dict):
    """
    Dado o dicionário {outcome: {price, bookmaker}}, calcula se existe
    surebet, o percentual de lucro e a divisão de stake ideal.

    Retorna None se não houver arbitragem, ou um dict com os detalhes.
    """
    if len(best_odds) < 2:
        return None

    inverse_sum = sum(1 / data["price"] for data in best_odds.values())

    if inverse_sum >= 1:
        return None  # sem arbitragem

    profit_percent = (1 / inverse_sum - 1) * 100

    stakes = {}
    for outcome, data in best_odds.items():
        stake = STAKE_EXAMPLE * (1 / data["price"]) / inverse_sum
        stakes[outcome] = {
            "stake": round(stake, 2),
            "price": data["price"],
            "bookmaker": data["bookmaker"],
        }

    return {
        "profit_percent": round(profit_percent, 2),
        "stakes": stakes,
        "guaranteed_return": round(STAKE_EXAMPLE / inverse_sum, 2),
    }


def format_alert(sport_title: str, event: dict, arb: dict) -> str:
    home = event.get("home_team", "")
    away = event.get("away_team", "")
    commence = event.get("commence_time", "")

    lines = [
        f"🎯 *SUREBET ENCONTRADA* — {arb['profit_percent']}% de lucro",
        f"🏆 {sport_title}",
        f"⚔️ {home} x {away}",
        f"🕒 Início: {commence}",
        "",
        f"💰 Simulação com R$ {STAKE_EXAMPLE:.0f} de banca total:",
    ]
    for outcome, data in arb["stakes"].items():
        lines.append(
            f"  • *{outcome}* — apostar R$ {data['stake']:.2f} "
            f"@ {data['price']} ({data['bookmaker']})"
        )
    lines.append("")
    lines.append(f"✅ Retorno garantido: R$ {arb['guaranteed_return']:.2f}")
    lines.append(
        "\n⚠️ Odds mudam rápido — confira nas casas antes de apostar. "
        "Confirme também se as casas aceitam o valor de stake calculado."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Varredura
# ---------------------------------------------------------------------------

def fetch_odds(sport: str):
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    resp = requests.get(ODDS_API_URL.format(sport=sport), params=params, timeout=20)
    if resp.status_code != 200:
        logger.warning("Falha ao buscar odds de %s: %s - %s", sport, resp.status_code, resp.text[:200])
        return []
    remaining = resp.headers.get("x-requests-remaining")
    if remaining is not None:
        logger.info("Requisições restantes na The Odds API: %s", remaining)
    return resp.json()


async def scan_once(app: Application):
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID não configurado ainda — mande /start no bot para descobrir o seu.")
        return

    found_any = False
    for sport in SPORTS:
        sport = sport.strip()
        if not sport:
            continue
        try:
            events = fetch_odds(sport)
        except Exception:
            logger.exception("Erro buscando odds de %s", sport)
            continue

        for event in events:
            event_id = event.get("id")
            best_odds = find_best_odds_per_outcome(event.get("bookmakers", []))
            arb = calculate_arbitrage(best_odds)

            if arb and arb["profit_percent"] >= MIN_PROFIT_PERCENT:
                alert_key = f"{event_id}:{arb['profit_percent']}"
                if alert_key in _already_alerted:
                    continue
                _already_alerted.add(alert_key)
                found_any = True

                message = format_alert(sport, event, arb)
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="Markdown",
                )

    if not found_any:
        logger.info("Varredura concluída, nenhuma surebet nova encontrada.")


async def scanner_loop(app: Application):
    """Loop de fundo que roda a varredura periodicamente."""
    while True:
        try:
            await scan_once(app)
        except Exception:
            logger.exception("Erro inesperado durante a varredura")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)


# ---------------------------------------------------------------------------
# Comandos do Telegram
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🤖 Bot de scanner de surebets ativo!\n\n"
        f"Seu chat_id é: `{chat_id}`\n"
        "Coloque esse valor na variável de ambiente TELEGRAM_CHAT_ID "
        "e reinicie o bot para começar a receber os alertas aqui.\n\n"
        "Comandos:\n"
        "/scan - forçar uma varredura agora\n"
        "/status - ver configuração atual",
        parse_mode="Markdown",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Status do scanner*\n"
        f"Esportes: {', '.join(SPORTS)}\n"
        f"Regiões: {REGIONS}\n"
        f"Lucro mínimo: {MIN_PROFIT_PERCENT}%\n"
        f"Intervalo: {SCAN_INTERVAL_MINUTES} min\n"
        f"Chat configurado: {'sim' if TELEGRAM_CHAT_ID else 'não — mande /start'}\n"
        f"Hora atual (UTC): {datetime.now(timezone.utc).strftime('%H:%M:%S')}",
        parse_mode="Markdown",
    )


async def scan_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando surebets agora, aguarde...")
    await scan_once(context.application)
    await update.message.reply_text("✅ Varredura concluída.")


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

async def post_init(app: Application):
    # Dispara o loop de varredura em segundo plano assim que o bot sobe
    asyncio.create_task(scanner_loop(app))


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("scan", scan_now))

    logger.info("Bot iniciado. Aguardando comandos e rodando varreduras a cada %s min.", SCAN_INTERVAL_MINUTES)
    app.run_polling()


if __name__ == "__main__":
    main()
