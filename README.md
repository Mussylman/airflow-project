# Apache Airflow + Celery + Selenium

Dockerized Apache Airflow with CeleryExecutor, PostgreSQL, Redis, and Selenium WebDriver — готов для продвинутых DAG'ов, включая автоматизацию через браузер.

---

## 🚀 Быстрый старт (на Linux)

```bash
# Клонируй репозиторий
git clone https://github.com/<your-username>/airflow-project.git
cd airflow-project

# Запусти Airflow + Redis + Postgres + Selenium
docker-compose up -d


##  📂 Структура проекта

.
├── dags/                  # DAG-файлы
├── logs/                  # Логи Airflow
├── plugins/               # (опционально) кастомные плагины
├── Dockerfile             # Образ для всех airflow-сервисов
├── docker-compose.yaml    # Описание сервисов (webserver, scheduler, worker, redis, postgres)
├── requirements.txt       # Зависимости для DAG'ов
└── .gitignore

