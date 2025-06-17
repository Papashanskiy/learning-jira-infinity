import os
import logging
from typing import List
from datetime import datetime
from jira import JIRA
from apscheduler.schedulers.blocking import BlockingScheduler
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Jira and OpenAI configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Field key for "Epic Link" in Jira (update if yours differs)
EPIC_LINK_FIELD = "customfield_10014"

# Status names in Jira workflow
STATUS_IN_PROGRESS = "In Progress"
STATUS_BACKLOG = "Backlog"
STATUS_DONE = "Done"

# Schedule: weekday -> list of (epic, topic)
PROJECT_SCHEDULE = {
    0: [("PRO-1", "English"), ("PRO-2", "Algorithms and Data Structures")],
    1: [("PRO-1", "English"), ("PRO-3", "System Design")],
    2: [("PRO-1", "English"), ("PRO-4", "Python and Development")],
    3: [("PRO-1", "English"), ("PRO-5", "ML Ops and DevOps")],
    4: [("PRO-1", "English"), ("PRO-6", "Databases and Data Engineering")],
}


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
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
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
