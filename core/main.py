import pytz
import logging

from typing import List, Optional, Tuple
from datetime import datetime
from jira import JIRA, Comment, Issue
from apscheduler.schedulers.blocking import BlockingScheduler
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ratelimiter import RateLimiter

from config import (
    DRY_RUN, 
    GROQ_API_KEY, 
    JIRA_PROJECT_KEY, 
    JIRA_TOKEN, 
    JIRA_URL, 
    JIRA_USER, 
    PROJECT_SCHEDULE, 
    SCHEDULER_DAYS, 
    SCHEDULER_HOUR, 
    SCHEDULER_MINUTE, 
    SCHEDULER_TIMEZONE, 
    STATUS_BACKLOG, 
    STATUS_IN_PROGRESS, 
    validate_config,
    JIRA_HISTORY_KEY
)

rate_limiter = RateLimiter(max_calls=20, period=60)


def init_clients() -> Tuple[JIRA, Groq]:
    validate_config()
    jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USER, JIRA_TOKEN))
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


@rate_limiter
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


def generate_new_task(groq_client: Groq, topic_history: str, topic: str) -> dict:
    prompt = (
        f"У меня уже были темы: {topic_history}. "
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


def seek_topic_history_comment(comments: List[Comment], epic_key: str) -> Optional[Comment]:
    for comment in comments:
        lines = comment.body.splitlines()
        for line in lines:
            if 'Ключ топика' in line:
                if epic_key in line:
                    return comment
                break


def create_topic_history_comment(jira: JIRA, epic_key: str, topic: str):
    comment_body = f'Топик: {topic}\nКлюч топика: {epic_key}\n\nИстория топика:'
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would create comment in issue {JIRA_HISTORY_KEY} with body'{comment_body}'")
        return
    jira_add_comment(jira, JIRA_HISTORY_KEY, comment_body)


def update_topic_history(comment: Comment, new_theme: str):
    comment_body = comment.body + f'\n{new_theme}'
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would update comment in issue {JIRA_HISTORY_KEY} to '{comment_body}'")
        return
    comment.update(body=comment_body)


def parse_history_comment(topic_comment: str) -> str:
    """
    Извлекает список тем из секции "История топика:" в переданном тексте.
    Если секция не найдена, возвращает пустую строку.
    """
    lines = topic_comment.splitlines()
    result_lines = []
    recording = False

    for line in lines:
        stripped = line.strip()
        if recording:
            if stripped:
                result_lines.append(stripped)
        elif stripped.startswith("История топика"):
            # Как только встречаем метку, включаем сбор последующих строк
            recording = True

    return "\n".join(result_lines)


def get_topic_history(jira: JIRA, epic_key: str, topic: str) -> str:
    try:
        history_issue = jira.issue(JIRA_HISTORY_KEY)
        history_comments = history_issue.fields.comment.comments
        topic_comment = seek_topic_history_comment(history_comments, epic_key)
        if not topic_comment:
            create_topic_history_comment(jira, epic_key, topic)
        passed_themes: str = parse_history_comment(topic_comment.body)
        return passed_themes
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


def process_project(jira: JIRA, groq_client: Groq, epic_key: str, topic: str, history: str):
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
        in_progress_issues = jira_search_issues(jira, jql_ip)
        if in_progress_issues:
            key = in_progress_issues[0].key
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
        backlog_issues = jira_search_issues(jira, jql_bl)
        if backlog_issues:
            issue = backlog_issues[0]
            transition_issue_to_status(jira, issue, STATUS_IN_PROGRESS)
            notify(
                jira,
                issue.key,
                (
                    f"Задача по теме '{topic}' переведена в статус 'В работе'. "
                    "Отличная возможность продолжить обучение! Удачи и приятного изучения 🚀"
                )
            )
            theme = issue.fields.summary
            history_comments = issue.fields.comment.comments
            topic_history_comment: str = seek_topic_history_comment(history_comments, epic_key)
            update_topic_history(topic_history_comment, theme)
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
            'issuetype': {'name': 'Task'},
        })
        
        
        theme = new_issue.fields.summary
        history_comments = new_issue.fields.comment.comments
        topic_history_comment: str = seek_topic_history_comment(history_comments, epic_key)
        update_topic_history(topic_history_comment, theme)

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
        history: str = get_topic_history(jira, epic, topic)
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
