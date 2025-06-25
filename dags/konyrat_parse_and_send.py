from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime
import pendulum
import logging
from helpers.telegram_loggerr import create_telegram_logger

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

# 🌐 Временная зона Алматы
local_tz = pendulum.timezone("Asia/Almaty")

# 🔧 Конфигурация Telegram
BOT_TOKEN = Variable.get("konyrat_bot_token")
CHAT_ID = Variable.get("konyrat_bot_chat_id")
logger = create_telegram_logger(BOT_TOKEN, CHAT_ID)

def parse_qoldau():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # подключение к удалённому selenium (в docker-сервисе selenium)
    driver = webdriver.Remote(
        command_executor='http://selenium:4444/wd/hub',
        options=options
    )

    driver.get("https://cgr.qoldau.kz/ru/start")
    time.sleep(5)
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")

    target_title = "Нур Жолы - Хоргос"
    title_blocks = soup.select(".col-md-4.font-14.square-chart-name")
    square_blocks = soup.select(".col-md-8.square-chart-container")

    target_index = next(
        (idx for idx, block in enumerate(title_blocks) if block.text.strip() == target_title),
        -1
    )

    if target_index == -1 or target_index >= len(square_blocks):
        logger.error("❌ Направление 'Нур Жолы - Хоргос' не найдено")
        return

    squares = square_blocks[target_index].select(".square")
    result = []

    for sq in squares:
        tooltip = sq.get("data-original-title", "")
        if not tooltip:
            continue

        text = re.sub(r"<[^>]+>", "", tooltip).strip()

        if "Выходной день" in text:
            date_match = re.search(r"(\d+ \w+)", text)
            result.append({
                "дата": date_match.group(1) if date_match else "неизвестно",
                "Выходной": True,
                "Мрп 1": None,
                "Мрп 100": None
            })
            continue

        date_match = re.search(r"Свободно на (\d+ \w+)", text)
        m1_match = re.search(r"за 1 МРП: (\d+)", text)
        m100_match = re.search(r"за 100 МРП: (\d+)", text)

        result.append({
            "дата": date_match.group(1) if date_match else "неизвестно",
            "Выходной": False,
            "Мрп 1": int(m1_match.group(1)) if m1_match else None,
            "Мрп 100": int(m100_match.group(1)) if m100_match else None
        })

    # 🎯 Фильтрация
    filtered_result = []
    for entry in result:
        if not entry["Выходной"] and (entry["Мрп 1"] is None or entry["Мрп 1"] == 0):
            continue

        filtered_result.append({
            "дата": entry["дата"],
            "Выходной": entry["Выходной"],
            "Мрп 1": entry["Мрп 1"]
        })

    if not filtered_result:
        logger.info("ℹ️ Нет актуальных данных для отображения.")
        return

    # ✉️ Формируем сообщение
    message_lines = [f"🛣 Направление: {target_title}"]
    for entry in filtered_result:
        if entry["Выходной"]:
            message_lines.append(f"{entry['дата']} — Выходной")
        elif entry["Мрп 1"] is not None:
            message_lines.append(f"{entry['дата']} — за 1 МРП: {entry['Мрп 1']}")

    message = "\n".join(message_lines)
    logger.info(message)

# 🕒 DAG
with DAG(
    dag_id="konyrat_parse_and_send",
    schedule_interval="0 * * * *",  # каждый час в начале часа
    start_date=datetime(2025, 1, 1, tzinfo=local_tz),
    catchup=False,
    access_control={
        "Admin": {"can_read", "can_edit"},
        # только роль "Admin" сможет видеть и управлять этим DAG
    },
    tags=["qoldau", "parser"]
) as dag:

    parse_task = PythonOperator(
        task_id="parse_and_send",
        python_callable=parse_qoldau
    )
