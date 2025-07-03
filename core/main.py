import pytz
import logging

from typing import List, Optional, Tuple
from datetime import datetime
from jira import JIRA, Comment, Issue
from apscheduler.schedulers.blocking import BlockingScheduler
from groq import Groq
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)

from config import (
    DRY_RUN,
    GROQ_API_KEY,
    GROQ_MODEL,
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
    TELEGRAM_CHAT_ID,
    TELEGRAM_SEND_MESSAGE_URL,
    validate_config,
    JIRA_HISTORY_KEY,
)


def init_clients() -> Tuple[JIRA, Groq]:
    validate_config()
    jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USER, JIRA_TOKEN))
    groq_client = Groq(api_key=GROQ_API_KEY)
    return jira, groq_client


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_search_issues(jira: JIRA, jql: str, maxResults: int = 1000):
    return jira.search_issues(jql, maxResults=maxResults)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_create_issue(jira: JIRA, fields: dict):
    return jira.create_issue(fields=fields)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_transition_issue(jira: JIRA, issue: Issue, transition_id):
    return jira.transition_issue(issue, transition_id)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_add_comment(jira: JIRA, issue_key: str, message: str):
    return jira.add_comment(issue_key, message)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_issue(jira: JIRA, issue_key: str):
    return jira.issue(issue_key)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def jira_update_issue(issue: Issue, issue_fields):
    return issue.update(fields=issue_fields)


def notify(issue_key: str, message: str):
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would send message to telegram")
        return
    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(TELEGRAM_SEND_MESSAGE_URL, data=payload)
    except Exception as e:
        logging.error(
            f"Failed to send message to telegram for {issue_key}: {e}", exc_info=True)


def notify_critical_error(message: str):
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would send CRITICAL message to telegram: {message}")
        return
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(TELEGRAM_SEND_MESSAGE_URL, data=payload)
    logging.error(f"CRITICAL: {message}")


def is_groq_notfound_error(e):
    return hasattr(e, "__class__") and e.__class__.__name__ == "NotFoundError"


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=(
        retry_if_exception_type(Exception) &
        retry_if_exception(lambda e: is_groq_notfound_error(e)
                           or isinstance(e, Exception))
    ),
    reraise=True,
)
def call_groq_generate_content(groq_client: Groq, prompt: str) -> str:
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would call Groq API with prompt: {prompt}")
        return "# DRY-RUN\nОписание задачи (DRY-RUN)"
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=GROQ_MODEL,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        # Специальная обработка NotFoundError от groq
        if is_groq_notfound_error(e):
            logging.error(f"Groq API NotFoundError: {e}", exc_info=True)
            # Пробрасываем исключение, чтобы tenacity сделал retry
            raise
        raise


def generate_new_task(groq_client: Groq, topic_history: str, topic: str) -> dict:
    prompt = (
        f"У меня уже были темы: {topic_history}. "
        f"Сгенерируй обучающий материал по разделу '{topic}'. "
        "Мне нужно это для подготовки к собеседованию. "
        "Сделай это в формате подходящим для описания задачи в "
        "Jira, чтобы я мог легко скопировать и вставить в Jira. "
        "Метирал должен быть всеобьемлющим и должен полностью "
        "покрывать тему, включая ссылки на полезные ресурсы, примеры и объяснения. "
        "Мне важно сформировать навык глубоких ответов на вопросы интервьюера, "
        "в связи с чем так же покажи мне как могут выглядеть "
        "глубокие ответы на вопросы из этого топика. "
        "В результате я ожидаю получить текст, который я смогу распарсить. "
        "Нужно явно указать заголовок, который будет являться темой. "
        "Заголовок должен быть в формате '# Тема'. "
        "Чтобы я мог достатать заголово таким кодом "
        "summary = content.splitlines()[0].lstrip('# ').strip()"
    )
    try:
        content = call_groq_generate_content(groq_client, prompt)
        summary = content.splitlines()[0].lstrip("# ").strip()
        return {"summary": summary, "description": content}
    except Exception as e:
        # Если это NotFoundError, возвращаем заглушку, чтобы не падал процесс
        if hasattr(e, "__class__") and e.__class__.__name__ == "NotFoundError":
            summary = "Ошибка Groq API"
            description = "# Ошибка Groq API: модель не найдена или недоступна.\nПожалуйста, проверьте настройки модели или обратитесь к администратору."
            logging.error(
                f"Groq NotFoundError in generate_new_task: {e}", exc_info=True)
            return {"summary": summary, "description": description}
        logging.error(f"Groq API error after retries: {e}", exc_info=True)
        raise


def generate_description_for_existing_task(groq_client: Groq, topic: str, theme: str) -> dict:
    prompt = (
        f"Сгенерируй обучающий материал по разделу '{topic}' на тему '{theme}'. "
        "Мне нужно это для подготовки к собеседованию. "
        "Сделай это в формате подходящим для описания задачи в "
        "Jira, чтобы я мог легко скопировать и вставить в Jira. "
        "Метирал должен быть всеобьемлющим и должен полностью "
        "покрывать тему, включая ссылки на полезные ресурсы, примеры и объяснения. "
        "Мне важно сформировать навык глубоких ответов на вопросы интервьюера, "
        "в связи с чем так же покажи мне как могут выглядеть "
        "глубокие ответы на вопросы из этого топика. "
        "В результате я ожидаю получить текст, который я смогу распарсить. "
        "Нужно явно указать заголовок, который будет являться темой. "
        "Заголовок должен быть в формате '# Тема'. "
        "Чтобы я мог достатать заголово таким кодом "
        "summary = content.splitlines()[0].lstrip('# ').strip()"
    )
    try:
        content = call_groq_generate_content(groq_client, prompt)
        summary = content.splitlines()[0].lstrip("# ").strip()
        return {"summary": summary, "description": content}
    except Exception as e:
        if hasattr(e, "__class__") and e.__class__.__name__ == "NotFoundError":
            summary = "Ошибка Groq API"
            description = "# Ошибка Groq API: модель не найдена или недоступна.\nПожалуйста, проверьте настройки модели или обратитесь к администратору."
            logging.error(
                f"Groq NotFoundError in generate_description_for_existing_task: {e}", exc_info=True)
            return {"summary": summary, "description": description}
        logging.error(f"Groq API error after retries: {e}", exc_info=True)
        raise


def seek_topic_history_comment(
    comments: List[Comment], epic_key: str
) -> Optional[Comment]:
    for comment in comments:
        lines = comment.body.splitlines()
        for line in lines:
            if "Ключ топика" in line:
                if epic_key in line:
                    return comment
                break


def create_topic_history_comment(jira: JIRA, epic_key: str, topic: str):
    comment_body = f"Топик: {topic}\nКлюч топика: {epic_key}\n\nИстория топика:"
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would create comment in issue {JIRA_HISTORY_KEY} with body'{comment_body}'"
        )
        return
    jira_add_comment(jira, JIRA_HISTORY_KEY, comment_body)


def update_topic_history(jira: JIRA, epic_key: str, new_theme: str):
    history_issue = jira.issue(JIRA_HISTORY_KEY)
    history_comments = history_issue.fields.comment.comments
    topic_history_comment: Optional[Comment] = seek_topic_history_comment(
        history_comments, epic_key)
    if topic_history_comment:
        comment_body = topic_history_comment.body + f"\n{new_theme}"
        if DRY_RUN:
            logging.info(
                f"[DRY-RUN] Would update comment in issue {JIRA_HISTORY_KEY} to '{comment_body}'"
            )
            return
        topic_history_comment.update(body=comment_body)
    else:
        logging.warning(
            f"No topic comment found for epic {epic_key} after supposed creation.")
        # Не пытаемся обращаться к .body


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
            return ""
        passed_themes: str = parse_history_comment(topic_comment.body)
        return passed_themes
    except Exception as e:
        logging.error(
            f"Error fetching history for {epic_key}: {e}", exc_info=True)
        return ""


def transition_issue_to_status(jira: JIRA, issue: Issue, status_name: str):
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would transition issue {issue.key} to '{status_name}'")
        return
    try:
        transitions = jira.transitions(issue)
        transition_id = next(t["id"]
                             for t in transitions if t["name"] == status_name)
        jira_transition_issue(jira, issue, transition_id)
        logging.info(f"Issue {issue.key} transitioned to '{status_name}'")
    except StopIteration:
        logging.error(
            f"No transition found for status '{status_name}' on issue {issue.key}",
            exc_info=True,
        )
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


def process_project(
    jira: JIRA, groq_client: Groq, epic_key: str, topic: str, history: str
):
    try:
        if not epic_exists(jira, epic_key):
            msg = f"Skipping topic '{topic}' because epic '{epic_key}' does not exist or is inaccessible."
            logging.error(msg)
            notify_critical_error(msg)
            return

        # Check "In Progress" tasks in the epic
        jql_ip = (
            f"project = {JIRA_PROJECT_KEY} "
            f'AND status = "{STATUS_IN_PROGRESS}" '
            f"AND parent = {epic_key}"
        )
        in_progress_issues = jira_search_issues(jira, jql_ip)
        if in_progress_issues:
            key = in_progress_issues[0].key
            # TODO сделать так, чтобы gpt подсказывала как пройти этот тикет
            notify(
                key,
                (
                    f"У тебя уже есть задача в топике '{topic}' на тему '{in_progress_issues[0].fields.summary}' в статусе 'В работе'! "
                    f"Ссылка на задачу: {JIRA_URL + '/browse/' + key}. "
                    "Продолжай учиться — ты на верном пути 🚀 Если возникнут вопросы, "
                    "не стесняйся их записывать прямо в задаче. Вперёд к новым знаниям и успехам! 💡"
                ),
            )
            return

        # Move backlog task to In Progress
        jql_bl = (
            f"project = {JIRA_PROJECT_KEY} "
            f'AND status = "{STATUS_BACKLOG}" '
            f"AND parent = {epic_key} "
            "ORDER BY key DESC"
        )
        backlog_issues = jira_search_issues(jira, jql_bl)
        if backlog_issues:
            issue = backlog_issues[0]
            if DRY_RUN:
                logging.info(
                    "[DRY-RUN] Would update issue status in epic "
                    f"'{epic_key}' with summary '{task['summary']}' "
                    f"from '{issue.fields.status}' to '{STATUS_IN_PROGRESS}'"
                )
            else:
                transition_issue_to_status(jira, issue, STATUS_IN_PROGRESS)
            if not issue.fields.description:
                existed_task = generate_description_for_existing_task(
                    groq_client, topic, issue.fields.summary)
                if DRY_RUN:
                    logging.info(
                        "[DRY-RUN] Would update issue description in epic "
                        f"'{epic_key}' with summary '{task['summary']}' to "
                        f"{existed_task['description']}"
                    )
                else:
                    jira_update_issue(
                        issue, {'description': existed_task['description']})
            notify(
                issue.key,
                (
                    f"Задача в топике '{topic}' на тему '{issue.fields.summary}' переведена в статус 'В работе'. "
                    f"Ссылка на задачу: {JIRA_URL + '/browse/' + issue.key}. "
                    "Отличная возможность продолжить обучение! Удачи и приятного изучения 🚀"
                ),
            )
            theme = issue.fields.summary
            update_topic_history(jira, epic_key, theme)
            return

        # Create a new task under the epic
        task = generate_new_task(groq_client, history, topic)
        if DRY_RUN:
            logging.info(
                f"[DRY-RUN] Would create issue in epic '{epic_key}' with summary '{task['summary']}'"
            )
            return

        new_issue = jira_create_issue(
            jira,
            {
                "project": {"key": epic_key.split("-")[0]},
                "parent": {"key": epic_key},
                "summary": task["summary"],
                "description": task["description"],
                "issuetype": {"name": "Task"},
            },
        )

        theme = new_issue.fields.summary
        update_topic_history(jira, epic_key, theme)

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
            text = (
                f"Создана и переведена в рабочий статус новая задача "
                f"в топике {topic} на тему {new_issue.fields.summary}. "
                f"Ссылка на задачу: {JIRA_URL + '/browse/' + new_issue.key}"
            )
            notify(new_issue.key, text)
    except Exception as e:
        msg = f"Error processing {epic_key}: {e}"
        logging.error(msg, exc_info=True)
        notify_critical_error(msg)


def run_daily():
    jira, groq_client = init_clients()
    # Для тестов: если datetime подменён, корректно вызываем today().weekday(self)
    today_func = getattr(datetime, "today", None)
    if callable(today_func):
        today_obj = today_func()
        weekday_func = getattr(today_obj, "weekday", None)
        if callable(weekday_func):
            try:
                today = weekday_func(today_obj)
            except TypeError:
                # Для обычного datetime weekday(self), для monkeypatch — без self
                today = weekday_func()
        else:
            today = 0
    else:
        today = 0
    for epic, topic in PROJECT_SCHEDULE.get(today, []):
        try:
            history: str = get_topic_history(jira, epic, topic)
            process_project(jira, groq_client, epic, topic, history)
        except Exception as e:
            logging.error(
                f"Exception in run_daily for epic={epic}, topic={topic}: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    validate_config()
    scheduler = BlockingScheduler(timezone=pytz.timezone(SCHEDULER_TIMEZONE))
    scheduler.add_job(
        run_daily,
        "cron",
        day_of_week=SCHEDULER_DAYS,
        hour=SCHEDULER_HOUR,
        minute=SCHEDULER_MINUTE,
        misfire_grace_time=3600,
    )
    logging.info("Starting Jira automation...")
    scheduler.start()
