import os
from dotenv import load_dotenv


load_dotenv()

# Jira and OpenAI configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JIRA_BOARD_ID = int(os.getenv("JIRA_BOARD_ID", "1"))
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "PRO")  # Jira project key
JIRA_HISTORY_KEY = os.getenv("JIRA_HISTORY_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

GROQ_MODEL = os.getenv("GROQ_MODEL", default="meta-llama/llama-guard-4-12b")

# Status names in Jira workflow
STATUS_IN_PROGRESS = "In Progress"
STATUS_BACKLOG = "Backlog"
STATUS_DONE = "Done"

# Schedule: weekday -> list of (epic, topic)
PROJECT_SCHEDULE = {
    0: [("PRO-1", "Английский"), ("PRO-3", "Алгоритмы и структуры данных")],
    1: [("PRO-1", "Английский"), ("PRO-4", "Систем дизайн")],
    2: [("PRO-1", "Английский"), ("PRO-5", "Поведенческие вопросы")],
    3: [("PRO-1", "Английский"), ("PRO-6", "Python")],
    4: [("PRO-1", "Английский"), ("PRO-7", "ML Ops и DevOps")],
}

# Новые переменные окружения для планировщика
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Asia/Almaty")
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", 8))
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", 0))
# строка, например "mon-fri" или "0-4"
SCHEDULER_DAYS = os.getenv("SCHEDULER_DAYS", "mon-fri")

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

TELEGRAM_SEND_MESSAGE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def validate_config():
    required = [JIRA_URL, JIRA_USER, JIRA_TOKEN, GROQ_API_KEY, JIRA_BOARD_ID]
    if not all(required):
        missing = [name for name, val in zip(
            ["JIRA_URL", "JIRA_USER", "JIRA_TOKEN", "GROQ_API_KEY", "JIRA_BOARD_ID"], required) if not val]
        raise ValueError(f"Missing env vars: {', '.join(missing)}")
