import logging
from typing import List, Optional

from jira import Comment, Issue

from config import JIRA_HISTORY_KEY, JIRA_PROJECT_KEY, STATUS_DONE
from main import (
    call_groq_generate_content, 
    create_topic_history_comment, 
    init_clients, 
    jira_search_issues,
    parse_history_comment, 
    seek_topic_history_comment, 
    update_topic_history
)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    jira, groq_client = init_clients()

    epics = [
        ("PRO-1", "Английский"),
        ("PRO-3", "Алгоритмы и структуры данных"),
        ("PRO-4", "Систем дизайн"),
        ("PRO-5", "Поведенческие вопросы"),
        ("PRO-6", "Python"),
        ("PRO-7", "ML Ops и DevOps")
    ]

    for epic_key, epic_title in epics:
        jql_done_issues = (
            f'project = {JIRA_PROJECT_KEY} '
            f'AND status = "{STATUS_DONE}" '
            f'AND parent = {epic_key} '
        )
        done_issues: List[Issue] = jira_search_issues(jira, jql_done_issues)

        history_issue = jira.issue(JIRA_HISTORY_KEY)
        history_comments = history_issue.fields.comment.comments
        topic_history_comment = seek_topic_history_comment(history_comments, epic_key)
        
        if not topic_history_comment:
            topic_history_comment = create_topic_history_comment(jira, epic_key, epic_title)
            logging.info(f'Creat history for topic {epic_title}')
            continue
        
        topic_history = parse_history_comment(topic_history_comment.body)

        if topic_history:
            continue

        if not done_issues:
            continue

        themes = []
        for issue in done_issues:
            summary = issue.fields.summary
            description = issue.fields.description
            comments_bodies = [i.body for i in issue.fields.comment.comments]
            comments_text = '\n\n'.join(comments_bodies)
            issue_prompt = (
                'Твоя задача определить тему или список тем, которые были затронуты '
                'в низлежащей задаче. Я приложу название задачи, её описание и комментарии, '
                'которые были в этой задаче. В ответе я ожидаю получить только тему или список тем '
                'без каких либо других комментариев. Клади в темы только те темы, которые относятся к '
                f'топику {epic_title}. Если например топик на тему английского, то не надо класть туда '
                'темы по типу тайм менеджмент и тп. '
                '\n\n'
                'Пример ответа, где есть одна тема: \n'
                'Быстрая сортировка. \n\n'
                'Пример ответа, где есть несколько тем: \n'
                'Артикли\n'
                'Present Simple\n\n'
                f'Название задачи: {summary}\n'
                f'Описание задачи: {description}\n'
                f'Комментарии:\n {comments_text}'
            )
            logging.info(f'Getting theme from issue {issue.key}: {summary}')
            try:
                issue_themes = call_groq_generate_content(groq_client, issue_prompt)
                themes.append(issue_themes)
            except Exception as e:
                logging.error(f"Error getting theme from issue {issue.key}: {e}", exc_info=True)
                continue

        if not themes:
            continue

        themes_text = '\n'.join(themes)
        final_prompt = (
            'Твоя задача из списка тем оставить только уникальные темы и в '
            'ответ написать только список, без твоих комментариев и умозаключений. '
            'Ответ дай без нумирации. Просто темы, разделенные переносом строки. '
            '\n'
            f'Список тем:\n{themes_text}'
        )
        try:
            final_themes = call_groq_generate_content(groq_client, final_prompt)
        except Exception as e:
            logging.error(f"Error getting final themes for epic {epic_key}: {e}", exc_info=True)
            continue

        history_issue = jira.issue(JIRA_HISTORY_KEY)
        history_comments = history_issue.fields.comment.comments
        topic_history_comment: Optional[Comment] = seek_topic_history_comment(history_comments, epic_key)

        if topic_history_comment:
            update_topic_history(topic_history_comment, final_themes)
        else:
            logging.warning(f"No topic comment found for epic {epic_key} after supposed creation.")


if __name__ == '__main__':
    main()
