import logging
from typing import List
from datetime import datetime
from jira import JIRA, Issue
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time
import pytz

# Load environment variables from .env file
load_dotenv()

# Jira and OpenAI configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JIRA_BOARD_ID = int(os.getenv("JIRA_BOARD_ID"))
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "PRO")  # Jira project key

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


def validate_config():
    required = [JIRA_URL, JIRA_USER, JIRA_TOKEN, GROQ_API_KEY, JIRA_BOARD_ID]
    if not all(required):
        missing = [name for name, val in zip(
            ["JIRA_URL", "JIRA_USER", "JIRA_TOKEN", "GROQ_API_KEY", "JIRA_BOARD_ID"], required) if not val]
        raise ValueError(f"Missing env vars: {', '.join(missing)}")


def init_clients() -> JIRA:
    validate_config()
    jira = JIRA(server=JIRA_URL, token_auth=(JIRA_USER, JIRA_TOKEN))
    groq_client = Groq(api_key=GROQ_API_KEY)
    return jira, groq_client


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def jira_search_issues(jira: JIRA, jql: str, maxResults: int = 1000):
    return jira.search_issues(jql, maxResults=maxResults)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def jira_create_issue(jira: JIRA, fields: dict):
    return jira.create_issue(fields=fields)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def jira_transition_issue(jira: JIRA, issue: Issue, transition_id):
    return jira.transition_issue(issue, transition_id)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def jira_add_comment(jira: JIRA, issue_key: str, message: str):
    return jira.add_comment(issue_key, message)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def jira_issue(jira: JIRA, issue_key: str):
    return jira.issue(issue_key)


def notify(jira: JIRA, issue_key: str, message: str):
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would add comment to {issue_key}: {message}")
        return
    try:
        jira_add_comment(jira, issue_key, message)
        logging.info(f"Notification added to {issue_key}")
    except Exception as e:
        logging.error(f"Failed to comment on {issue_key}: {e}", exc_info=True)


def call_groq_generate_content(groq_client: Groq, prompt: str) -> str:
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would call Groq API with prompt: {prompt}")
        return "# DRY-RUN\nОписание задачи (DRY-RUN)"
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
    )
    return chat_completion.choices[0].message.content


def generate_new_task(groq_client: Groq, topic_history: List[Issue], topic: str) -> dict:
    history_summary = [h.summary for h in topic_history]
    prompt = (
        f"У меня уже были темы: {', '.join(history_summary)}. "
        f"Сгенерируй обучающий материал по разделу '{topic}'. "
        "Мне нужно это для подготовки к собеседованию. "
        "Сделай это в формате Markdown, чтобы я мог "
        "легко скопировать и вставить в Jira. "
        "Метирал должен быть всеобьемлющим и должен полностью "
        "покрывать тему, включая ссылки на полезные ресурсы, примеры и объяснения. "
        "В результате я ожидаю получить текст, который я смогу распарсить. "
        "Нужно явно указать заголовок, который будет являться темой. Заголовок должен быть в формате '# Тема'. "
        "Чтобы я мог достатать заголово таким кодом summary = content.splitlines()[0].lstrip('# ').strip()"
    )
    try:
        content = call_groq_generate_content(groq_client, prompt)
        summary = content.splitlines()[0].lstrip('# ').strip()
        return {"summary": summary, "description": content}
    except Exception as e:
        logging.error(f"Groq API error after retries: {e}", exc_info=True)
        raise


def get_topic_history(jira: JIRA, epic_key: str, topic: str) -> List[Issue]:
    try:
        jql = (
            f'project = {JIRA_PROJECT_KEY} '
            f'AND status = "{STATUS_DONE}" '
            f'AND parent = {epic_key} '
            'ORDER BY updated DESC'
        )
        issues = jira_search_issues(jira, jql, maxResults=1000)
        return [issue for issue in issues]
    except Exception as e:
        logging.error(
            f"Error fetching history for {epic_key}: {e}", exc_info=True)
        return []


def transition_issue_to_status(jira: JIRA, issue: Issue, status_name: str):
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would transition issue {issue.key} to '{status_name}'")
        return
    try:
        transitions = jira.transitions(issue)
        transition_id = next(
            t['id'] for t in transitions if t['name'] == status_name
        )
        jira_transition_issue(jira, issue, transition_id)
        logging.info(f"Issue {issue.key} transitioned to '{status_name}'")
    except StopIteration:
        logging.error(
            f"No transition found for status '{status_name}' on issue {issue.key}", exc_info=True)
    except Exception as e:
        logging.error(
            f"Failed to transition issue {issue.key}: {e}", exc_info=True)


def epic_exists(jira: JIRA, epic_key: str) -> bool:
    """Проверяет, существует ли эпик и доступен ли он."""
    try:
        epic = jira_issue(jira, epic_key)
        # Можно добавить дополнительные проверки, например, статус эпика
        return True
    except Exception as e:
        logging.error(
            f"Epic {epic_key} not found or inaccessible: {e}", exc_info=True)
        return False


def notify_critical_error(message: str):
    # TODO: Реализовать отправку в Telegram/Slack или другой канал оповещений
    logging.error(f"CRITICAL: {message}")


def process_project(jira: JIRA, groq_client: Groq, epic_key: str, topic: str, history: List[Issue]):
    try:
        if not epic_exists(jira, epic_key):
            msg = f"Skipping topic '{topic}' because epic '{epic_key}' does not exist or is inaccessible."
            logging.error(msg)
            notify_critical_error(msg)
            return

        # Check "In Progress" tasks in the epic
        jql_ip = (
            f'project = {JIRA_PROJECT_KEY} '
            f'AND status = "{STATUS_IN_PROGRESS}" '
            f'AND parent = {epic_key}'
        )
        ip_issues = jira_search_issues(jira, jql_ip)
        if ip_issues:
            key = ip_issues[0].key
            # TODO сделать так, чтобы gpt подсказывала как пройти этот тикет
            notify(
                jira,
                key,
                (
                    f"У тебя уже есть задача по теме '{topic}' в статусе 'В работе'! "
                    "Продолжай учиться — ты на верном пути 🚀 Если возникнут вопросы, "
                    "не стесняйся их записывать прямо в задаче. Вперёд к новым знаниям и успехам! 💡"
                )
            )
            return

        # Move backlog task to In Progress
        jql_bl = (
            f'project = {JIRA_PROJECT_KEY} '
            f'AND status = "{STATUS_BACKLOG}" '
            f'AND parent = {epic_key} '
            'ORDER BY priority DESC'
        )
        bl_issues = jira_search_issues(jira, jql_bl)
        if bl_issues:
            issue = bl_issues[0]
            transition_issue_to_status(jira, issue, STATUS_IN_PROGRESS)
            notify(
                jira,
                issue.key,
                (
                    f"Задача по теме '{topic}' переведена в статус 'В работе'. "
                    "Отличная возможность продолжить обучение! Удачи и приятного изучения 🚀"
                )
            )
            return

        # Idempotency: check if a similar task already exists (not Done)
        jql_check = (
            f'project = {JIRA_PROJECT_KEY} '
            f'AND summary ~ "{topic}" '
            f'AND parent = {epic_key} '
            f'AND status != "{STATUS_DONE}"'
        )
        existing = jira_search_issues(jira, jql_check)
        if existing:
            msg = f"Task for topic '{topic}' already exists in epic '{epic_key}', skipping creation."
            logging.info(msg)
            # Можно отправлять критические уведомления, если это важно
            return

        # Create a new task under the epic
        task = generate_new_task(groq_client, history, topic)
        if DRY_RUN:
            logging.info(
                f"[DRY-RUN] Would create issue in epic '{epic_key}' with summary '{task['summary']}'")
            return

        new_issue = jira_create_issue(jira, {
            'project': {'key': epic_key.split('-')[0]},
            'parent': {'key': epic_key},
            'summary': task['summary'],
            'description': task['description'],
            'issuetype': {'name': 'Task'}
        })

        # Проверка, что задача создана
        if not new_issue or not hasattr(new_issue, "key"):
            msg = f"Failed to create new issue for topic '{topic}' in epic '{epic_key}'"
            logging.error(msg, exc_info=True)
            notify_critical_error(msg)
            return

        # Проверка перехода статуса
        transition_issue_to_status(jira, new_issue, STATUS_IN_PROGRESS)
        # Проверка, что задача действительно в нужном статусе
        updated_issue = jira_issue(jira, new_issue.key)
        if getattr(updated_issue.fields.status, "name", None) != STATUS_IN_PROGRESS:
            msg = f"Issue {new_issue.key} did not transition to '{STATUS_IN_PROGRESS}'"
            logging.error(msg, exc_info=True)
            notify_critical_error(msg)
        else:
            notify(jira, new_issue.key, f"Created and moved new {topic} task.")
    except Exception as e:
        msg = f"Error processing {epic_key}: {e}"
        logging.error(msg, exc_info=True)
        notify_critical_error(msg)


def run_daily():
    jira, groq_client = init_clients()
    today = datetime.today().weekday()
    for epic, topic in PROJECT_SCHEDULE.get(today, []):
        history = get_topic_history(jira, epic, topic)
        process_project(jira, groq_client, epic, topic, history)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    validate_config()
    scheduler = BlockingScheduler(timezone=pytz.timezone(SCHEDULER_TIMEZONE))
    scheduler.add_job(
        run_daily,
        'cron',
        day_of_week=SCHEDULER_DAYS,
        hour=SCHEDULER_HOUR,
        minute=SCHEDULER_MINUTE,
        misfire_grace_time=3600
    )
    logging.info("Starting Jira automation...")
    scheduler.start()
