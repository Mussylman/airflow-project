from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine
from helpers import log_setup
from helpers.telegram_loggerr import create_telegram_logger  # ✅

import logging
import os

# ✅ Получаем переменные из Airflow
bot_token = Variable.get("telegram_bot_token")  # универсальный токен
chat_id = Variable.get("telegram_chat_id")  # отдельный ID под заказы

# ✅ Создаём логгер с параметрами
telegram_logger = create_telegram_logger(bot_token, chat_id)

# === Параметры DAG ===
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='check_orders_dag',
    start_date=datetime(2024, 1, 1),
    schedule_interval='0 7 * * *',
    catchup=False,
    default_args=default_args,
    tags=['orders', 'telegram'],
) as dag:

    start = DummyOperator(task_id='start')

    def get_data_inventory(date):
        conn = BaseHook.get_connection("conn_iventiry")
        engine = create_engine(
            f'postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}'
        )
        query = f"""
        SELECT * FROM public.orders WHERE created_at >= '{date}' ORDER BY created_at ASC
        """
        data = pd.read_sql_query(query, engine)
        return data

    def log_order_info(start_date, successful_order, unsuccessful_order):
        logging.info(f"=== Информация о заказах на дату: {start_date} ===")
        logging.info(f"Успешные заказы: {successful_order}")
        logging.info(f"Неуспешные заказы: {unsuccessful_order}")

    def run_check_orders(**context):
        logging.info("Запуск логики проверки заказов")

        start_date = datetime.strptime(context["ds"], "%Y-%m-%d").date()
        end_date = start_date

        current_d = start_date
        total_successful_order = 0
        total_unsuccessful_order = 0

        while current_d <= end_date:
            df = get_data_inventory(current_d)

            successful_order = (df.status == 3).sum()
            unsuccessful_order = (df.status != 3).sum()

            total_successful_order += successful_order
            total_unsuccessful_order += unsuccessful_order
            current_d += timedelta(days=1)

        log_order_info(start_date, total_successful_order, total_unsuccessful_order)

        message = (
            f"📦 Информация о заказах на дату: {start_date}\n"
            f"✅ Успешные заказы: {total_successful_order}\n"
            f"❌ Неуспешные заказы: {total_unsuccessful_order}"
        )
        telegram_logger.info(message)

    check_orders = PythonOperator(
        task_id='check_orders',
        python_callable=run_check_orders,
        provide_context=True,
    )

    start >> check_orders
