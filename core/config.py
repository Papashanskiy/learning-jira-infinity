import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

# Jira configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Jira workflow statuses
STATUS_IN_PROGRESS = "In Progress"
STATUS_BACKLOG = "Backlog"
STATUS_DONE = "Done"

# Project schedule configuration
PROJECT_SCHEDULE: Dict[int, List[Tuple[str, str]]] = {
    0: [
        ("PRO-1", "English"),
        ("PRO-2", "Algorithms and Data Structures")
    ],
    # ...existing schedule...
}

# OpenAI configuration
OPENAI_MODEL = "gpt-4"
OPENAI_TEMPERATURE = 0.7
