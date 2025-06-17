import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

# Jira configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Field key for "Epic Link" in Jira (update if yours differs)
EPIC_LINK_FIELD = "customfield_10014"

# Jira workflow statuses
STATUS_IN_PROGRESS = "In Progress"
STATUS_BACKLOG = "Backlog"
STATUS_DONE = "Done"

# Project schedule configuration
PROJECT_SCHEDULE: Dict[int, List[Tuple[str, str]]] = {
    0: [("PRO-1", "English"), ("PRO-2", "Algorithms and Data Structures")],
    1: [("PRO-1", "English"), ("PRO-3", "System Design")],
    2: [("PRO-1", "English"), ("PRO-4", "Python and Development")],
    3: [("PRO-1", "English"), ("PRO-5", "ML Ops and DevOps")],
    4: [("PRO-1", "English"), ("PRO-6", "Databases and Data Engineering")],
}

# OpenAI configuration
OPENAI_MODEL = "gpt-4"
OPENAI_TEMPERATURE = 0.7
