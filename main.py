import os
import requests
import logging
from datetime import datetime
import time
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global function to load environment variables
def load_env_variables():
    """Loads environment variables required for the action."""
    try:
        env_vars = {
            'telegram_token': os.getenv('TELEGRAM_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
            'github_token': os.getenv('GITHUB_TOKEN'),
            'repo_name': os.getenv('GITHUB_REPOSITORY'),
            'run_id': os.getenv('GITHUB_RUN_ID'),
            'current_job_name': os.getenv('GITHUB_JOB')
        }
        
        # Log environment variables for debugging (excluding sensitive data)
        logging.info(f"Loaded environment variables: REPO_NAME={env_vars['repo_name']}, RUN_ID={env_vars['run_id']}, CURRENT_JOB_NAME={env_vars['current_job_name']}")
        
        return env_vars
    except Exception as e:
        logging.error(f"Failed to load environment variables: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to check connection to Telegram
def check_telegram_connection(telegram_token):
    """Checks the connection to the Telegram API."""
    try:
        logging.info("Checking Telegram connection...")
        test_url = f"https://api.telegram.org/bot{telegram_token}/getMe"
        response = requests.get(test_url)
        if response.status_code == 200:
            logging.info("Successfully connected to Telegram API.")
        else:
            logging.error(f"Failed to connect to Telegram: {response.text}")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Error while checking Telegram connection: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to check GitHub API access using the GITHUB_TOKEN
def check_github_access(github_token, repo_name):
    """Checks access to the GitHub API and retrieves repository information."""
    try:
        logging.info("Checking GitHub API access...")
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/repos/{repo_name}'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        repo_info = response.json()
        logging.info(f"GitHub API access successful. Repo name: {repo_info['full_name']}")
        return repo_info
    except Exception as e:
        logging.error(f"GitHub API access failed: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to send a message to Telegram
def send_telegram_message(telegram_token, chat_id, message):
    """Sends a message to a Telegram chat."""
    try:
        logging.info("Preparing to send message to Telegram...")
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info("Message sent successfully to Telegram.")
        else:
            logging.error(f"Failed to send message: {response.text}")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Error while sending message to Telegram: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to calculate the duration of a job
def compute_duration(start_time, end_time):
    """Computes the duration between two datetime objects."""
    try:
        if end_time < start_time:
            logging.error("End time is earlier than start time")
            return "Invalid time"
        duration = end_time - start_time
        minutes, seconds = divmod(duration.seconds, 60)
        return f"{minutes}m {seconds}s"
    except Exception as e:
        logging.error(f"Error computing duration: {str(e)}", exc_info=True)
        return "N/A" # return a string instead of exiting

# Function to get detailed information about a workflow run based on run_id
def get_workflow_run(github_token, repo_name, run_id):
    """Retrieves information about a specific workflow run."""
    try:
        logging.info(f"Fetching workflow run {run_id} information...")
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/repos/{repo_name}/actions/runs/{run_id}'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        workflow_run = response.json()
        logging.info(f"Successfully fetched workflow run {run_id} information.")
        return workflow_run
    except Exception as e:
        logging.error(f"Failed to fetch workflow run: {str(e)}", exc_info=True)
        sys.exit(1)

# Fetch job information from GitHub API
def get_workflow_jobs(github_token, repo_name, run_id, current_job_name):
    """Fetches workflow job information and waits for completion of other jobs."""

    logging.info("Fetching workflow job information from GitHub API and waiting for other jobs to complete...")

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    url = f'https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/jobs'

    while True:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        jobs = response.json()

        pending_jobs = [job for job in jobs['jobs'] if job['name'] != current_job_name and job['status'] != 'completed']
        if not pending_jobs:
            logging.info("All other jobs have completed.")
            return jobs
        else:
            logging.info(f"Waiting for {len(pending_jobs)} job(s) to complete...")
            time.sleep(5)

# Function to calculate total duration from jobs, excluding the current job (Telegram notification job)
def calculate_total_duration(jobs, current_job_name):
    """Calculates total duration, excluding the current job."""

    total_duration = timedelta(0)
    for job in jobs['jobs']:
        if job['name'] == current_job_name:
            continue  # Skip the current job

        if job.get('started_at') and job.get('completed_at'):
            start_time = datetime.strptime(job['started_at'], '%Y-%m-%dT%H:%M:%SZ')
            end_time = datetime.strptime(job['completed_at'], '%Y-%m-%dT%H:%M:%SZ')
            total_duration += (end_time - start_time)
        
    return total_duration

# Map job conclusion to corresponding status icon
def get_status_icon(conclusion):
    """Maps job conclusion to a corresponding status icon."""
    status_icons = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "🚫",
        "skipped": "⏭️",
        "timed_out": "⏰",
        "neutral": "⚪",
        "action_required": "⚠️"
    }
    return status_icons.get(conclusion, "❓")

# Function to get workflow status line emoji based on conclusion
def get_workflow_status_emoji(conclusion):
    if conclusion == "success":
        return "🟩"  # Green line emoji for success
    elif conclusion == "failure":
        return "🟥"  # Red line emoji for failure
    elif conclusion == "cancelled":
        return "⬜"  # Grey line emoji for cancelled
    else:
        return "🟦"  # Blue line emoji for in-progress (changed from yellow)

# Format the message to be sent to Telegram
def format_telegram_message(workflow, jobs, current_job_name):
    """Formats the message to be sent to Telegram."""

    try:
        logging.info("Formatting the message for Telegram...")

        workflow_name = workflow.get('name', 'Unknown Workflow')
        run_number = str(workflow.get('run_number', '#'))
        event_type = workflow.get('event', 'workflow_dispatch')
        event_url = workflow.get('html_url', '')
        duration = compute_duration(datetime.strptime(workflow['created_at'], '%Y-%m-%dT%H:%M:%SZ'),
                                    datetime.strptime(workflow['updated_at'], '%Y-%m-%dT%H:%M:%SZ'))
        workflow_display_name = f"{workflow_name} #{run_number}"
        author_name = workflow['actor']['login']
        author_url = workflow['actor']['html_url']

        workflow_conclusion = workflow.get('conclusion')
        workflow_status_emoji = get_workflow_status_emoji(workflow_conclusion)

        message = f"{workflow_status_emoji} *Github Actions Notification*\n\n"

        message += f"🔄 _Event:_ `{event_type}` | ⚙️ _Workflow:_ [{workflow_display_name}]({event_url}) _completed in_ {duration}\n\n"

        if event_type == "pull_request":
            pr = workflow.get("pull_requests", [{}])[0]
            pr_title = pr.get("title", "Unknown Pull Request")
            pr_url = pr.get("html_url", event_url)
            message += f"🔗 [Pull Request: {pr_title}]({pr_url})\n\n"
        elif event_type == "push":
            commit_message = workflow.get("head_commit", {}).get("message", "No commit message")
            commit_url = f"{workflow['repository']['html_url']}/commit/{workflow.get('head_commit', {}).get('id', '')}"
            message += f"📝 [Commit: {commit_message}]({commit_url})\n\n"
        elif event_type == "release":
            release_name = workflow.get("release", {}).get("tag_name", "No release tag")
            release_url = workflow.get("release", {}).get("html_url", event_url)
            message += f"🔗 [Release: {release_name}]({release_url})\n\n"
        elif event_type == "workflow_dispatch":
            branch_name = workflow.get("head_branch", "No branch")
            message += f"🔗 Workflow dispatched on branch: `{branch_name}`\n\n"
        elif event_type == "create":
            ref_type = workflow.get("ref_type", "No ref type")
            ref_name = workflow.get("ref", "No ref name")
            ref_url = f"{workflow['repository']['html_url']}/tree/{ref_name}" if ref_name else ""
            message += f"🔗 [Created: {ref_type}]({ref_url}) {ref_name}\n\n"


        elif event_type == "delete":
            ref_type = workflow.get("ref_type", "No ref type")
            ref_name = workflow.get("ref", "No ref name")
            message += f"🗑️ Deleted: {ref_type} `{ref_name}`\n\n"

        elif event_type == "repository_dispatch":
            event_name = workflow.get("client_payload", {}).get("action", "No event action")
            message += f"🔗 Repository Dispatch event: `{event_name}`\n\n"

        elif event_type == "schedule":
            schedule = workflow.get("schedule", {}).get("cron", "No schedule")
            message += f"⏰ Scheduled event with cron: `{schedule}`\n\n"

        else:
            message += "🔗 [Event details]\n\n"

        message += f"👤 _Author:_ [{author_name}]({author_url})\n\n"

        message += "_Job Details:_ \n\n"
        left_column = []
        right_column = []

        filtered_jobs = [job for job in jobs['jobs'] if job['name'] != current_job_name]

        for i, job in enumerate(filtered_jobs):
            job_name = job['name']
            job_url = job['html_url']
            if job.get('started_at') and job.get('completed_at'):
                job_duration = compute_duration(datetime.strptime(job['started_at'], '%Y-%m-%dT%H:%M:%SZ'),
                                                datetime.strptime(job['completed_at'], '%Y-%m-%dT%H:%M:%SZ'))
            elif job.get('started_at'):
                job_duration = "(In progress)"
            else:
                job_duration = "(Not started)"

            job_conclusion = job.get('conclusion')
            job_icon = get_status_icon(job_conclusion)
            job_detail = f"{job_icon} [{job_name}]({job_url}) ({job_duration})"

            if i % 2 == 0:
                left_column.append(job_detail)
            else:
                right_column.append(job_detail)

        max_left_width = max(len(detail) for detail in left_column) if left_column else 0
        format_string = f"{{:<{max_left_width + 4}}} {{}}"

        max_lines = max(len(left_column), len(right_column))
        for i in range(max_lines):
            left = left_column[i] if i < len(left_column) else ""
            right = right_column[i] if i < len(right_column) else ""
            message += format_string.format(left, right) + "\n"

        repo_url = workflow['repository']['html_url']
        repo_name = workflow['repository']['full_name']
        message += f"\n📦 _Repository:_ [{repo_name}]({repo_url})"

        total_duration = calculate_total_duration(jobs, current_job_name)
        message += f"\n⏱️ _Total Workflow Duration (excluding this notification):_ {str(total_duration)}"


        logging.info("Message formatted successfully.")
        return message

    except Exception as e:
        logging.error(f"Error formatting the message: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        logging.info("Starting the Telegram notification action...")
        env = load_env_variables()
        check_telegram_connection(env['telegram_token'])
        repo_info = check_github_access(env['github_token'], env['repo_name'])

        workflow_run = get_workflow_run(env['github_token'], env['repo_name'], env['run_id'])
        workflow_jobs = get_workflow_jobs(env['github_token'], env['repo_name'], env['run_id'], env['current_job_name'])

        message = format_telegram_message(workflow_run, workflow_jobs, env['current_job_name'])

        send_telegram_message(env['telegram_token'], env['chat_id'], message)

        logging.info("Action completed successfully.")
    except Exception as e:
        logging.error(f"Action failed: {str(e)}", exc_info=True)
        sys.exit(1)
