import logging
from typing import List
from datetime import datetime
from jira import JIRA
from apscheduler.schedulers.blocking import BlockingScheduler
import openai

from config import (
    JIRA_URL,
    JIRA_USER,
    JIRA_TOKEN,
    OPENAI_API_KEY,
    EPIC_LINK_FIELD,
    STATUS_IN_PROGRESS,
    STATUS_BACKLOG,
    STATUS_DONE,
    PROJECT_SCHEDULE,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
)


def validate_config():
    required = [JIRA_URL, JIRA_USER, JIRA_TOKEN, OPENAI_API_KEY]
    if not all(required):
        missing = [name for name, val in zip(
            ["JIRA_URL", "JIRA_USER", "JIRA_TOKEN", "OPENAI_API_KEY"], required) if not val]
        raise ValueError(f"Missing env vars: {', '.join(missing)}")


def init_clients() -> JIRA:
    validate_config()
    jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USER, JIRA_TOKEN))
    openai.api_key = OPENAI_API_KEY
    return jira


def notify(jira: JIRA, issue_key: str, message: str):
    try:
        jira.add_comment(issue_key, message)
        logging.info(f"Notification added to {issue_key}")
    except Exception as e:
        logging.error(f"Failed to comment on {issue_key}: {e}")


def generate_new_task(topic_history: List[str], topic: str) -> dict:
    if topic == "English":
        prompt = (
            f"У меня уже были темы: {', '.join(topic_history)}. "
            "Create comprehensive interview prep for English interviews..."
        )
    else:
        prompt = (
            f"У меня уже были темы: {', '.join(topic_history)}. "
            f"Сгенерируй обучающий материал по '{topic}'..."
        )

    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=OPENAI_TEMPERATURE
    )
    content = response.choices[0].message.content.strip()
    summary = content.splitlines()[0].lstrip('# ').strip()
    return {"summary": summary, "description": content}


def get_topic_history(jira: JIRA, epic_key: str, topic: str) -> List[str]:
    try:
        jql = (
            f'"{EPIC_LINK_FIELD}" = "{epic_key}" '
            f'AND status = "{STATUS_DONE}" '
            f'AND summary ~ "Learning: {topic}" '
            'ORDER BY updated DESC'
        )
        issues = jira.search_issues(jql, maxResults=1000)
        return [issue.fields.summary.replace(f"Learning: {topic} - ", "") for issue in issues]
    except Exception as e:
        logging.error(f"Error fetching history for {epic_key}: {e}")
        return []


def process_project(jira: JIRA, epic_key: str, topic: str, history: List[str]):
    try:
        # Check "In Progress" tasks in the epic
        jql_ip = (
            f'"{EPIC_LINK_FIELD}" = "{epic_key}" '
            f'AND status = "{STATUS_IN_PROGRESS}"'
        )
        ip_issues = jira.search_issues(jql_ip, maxResults=1)
        if ip_issues:
            key = ip_issues[0].key
            notify(
                jira, key, f"Already In Progress for today's {topic} session.")
            return

        # Move backlog task to In Progress
        jql_bl = (
            f'"{EPIC_LINK_FIELD}" = "{epic_key}" '
            f'AND status = "{STATUS_BACKLOG}" '
            'ORDER BY priority DESC'
        )
        bl_issues = jira.search_issues(jql_bl, maxResults=1)
        if bl_issues:
            issue = bl_issues[0]
            jira.transition_issue(issue, transition=STATUS_IN_PROGRESS)
            notify(jira, issue.key, f"Moved to In Progress for {topic}.")
            return

        # Create a new task under the epic
        task = generate_new_task(history, topic)
        new_issue = jira.create_issue(fields={
            'project': {'key': epic_key.split('-')[0]},
            EPIC_LINK_FIELD: epic_key,
            'summary': task['summary'],
            'description': task['description'],
            'issuetype': {'name': 'Task'}
        })
        jira.transition_issue(new_issue, transition=STATUS_IN_PROGRESS)
        notify(jira, new_issue.key, f"Created and moved new {topic} task.")
    except Exception as e:
        logging.error(f"Error processing {epic_key}: {e}")


def run_daily():
    jira = init_clients()
    today = datetime.today().weekday()
    for epic, topic in PROJECT_SCHEDULE.get(today, []):
        history = get_topic_history(jira, epic, topic)
        process_project(jira, epic, topic, history)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    validate_config()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_daily, 'cron', day_of_week='mon-fri', hour=8, minute=0,
                      misfire_grace_time=3600)
    logging.info("Starting Jira automation...")
    scheduler.start()
