import os
import requests
import logging
from datetime import datetime, timedelta
import time
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global constants for Telegram API
TELEGRAM_API_URL = "https://api.telegram.org/bot{telegram_token}/getMe"
TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{telegram_token}/sendMessage"
TELEGRAM_PAYLOAD_TEMPLATE = {
    'chat_id': '{chat_id}',
    'text': '{message}',
    'parse_mode': 'Markdown'
}

# Global constants for GitHub API
GITHUB_API_URL = 'https://api.github.com/repos/{repo_name}'
GITHUB_WORKFLOW_RUN_URL = "https://api.github.com/repos/{repo_name}/actions/runs/{run_id}"
GITHUB_WORKFLOW_JOBS_URL = "https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/jobs"
GITHUB_HEADERS_TEMPLATE = {
    'Authorization': 'token {github_token}',
    'Accept': 'application/vnd.github.v3+json'
}
MAX_ATTEMPTS = 5
SLEEP_INTERVAL = 5  # seconds

def load_env_variables():
    """Loads required environment variables and logs them (excluding sensitive data)."""
    try:
        env_vars = {
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
            'current_job_name': os.getenv('GITHUB_JOB'),
            'github_token': os.getenv('GITHUB_TOKEN'),
            'repo_name': os.getenv('GITHUB_REPOSITORY'),
            'run_id': os.getenv('GITHUB_RUN_ID'),
            'telegram_token': os.getenv('TELEGRAM_TOKEN'),
        }

        logging.info(
            f"Loaded env vars: "
            f"REPO_NAME={env_vars['repo_name']}, "
            f"RUN_ID={env_vars['run_id']}, "
            f"CURRENT_JOB_NAME={env_vars['current_job_name']}"
        )
        return env_vars
    except KeyError as e:
        logging.error(f"Missing required environment variable: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to load environment variables: {e}", exc_info=True)
        sys.exit(1)

def check_telegram_connection(telegram_token):
    """Checks the connection to the Telegram API and logs the result."""
    try:
        logging.info("Checking Telegram connection...")
        url = TELEGRAM_API_URL.format(telegram_token=telegram_token)
        response = requests.get(url)
        logging.info(f"Telegram API request URL: {url}")
        logging.info(f"Telegram API response status code: {response.status_code}")
        response.raise_for_status() # Raise an exception for bad status codes
        logging.info("Successfully connected to Telegram API.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to connect to Telegram: {e}", exc_info=True)
        sys.exit(1)

def check_github_access(github_token, repo_name):
    """Checks GitHub API access and logs the result."""
    try:
        logging.info("Checking GitHub API access...")
        headers = {key: value.format(github_token=github_token) for key, value in GITHUB_HEADERS_TEMPLATE.items()}
        url = GITHUB_API_URL.format(repo_name=repo_name)
        response = requests.get(url, headers=headers)
        logging.info(f"GitHub API request URL: {url}")
        logging.info(f"GitHub API response status code: {response.status_code}")
        response.raise_for_status()
        repo_info = response.json()
        logging.info(f"GitHub API access successful. Repo name: {repo_info['full_name']}")
        return repo_info
    except requests.exceptions.RequestException as e:
        logging.error(f"GitHub API access failed: {e}", exc_info=True)
        sys.exit(1)

def send_telegram_message(telegram_token, chat_id, message):
    """Sends a Telegram message and logs the result."""
    try:
        logging.info("Sending message to Telegram...")
        url = TELEGRAM_SEND_MESSAGE_URL.format(telegram_token=telegram_token)
        payload = {
            key: value.format(chat_id=chat_id, message=message)
            for key, value in TELEGRAM_PAYLOAD_TEMPLATE.items()
        }
        response = requests.post(url, json=payload)
        logging.info(f"Telegram API request URL: {url}")
        logging.info(f"Telegram API response status code: {response.status_code}")
        response.raise_for_status()
        logging.info("Message sent successfully to Telegram.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram message: {e}", exc_info=True)
        sys.exit(1)

def compute_duration(start_time, end_time):
    """Computes duration between two datetime objects, handling potential errors."""
    try:
        if not start_time or not end_time:  # Check for None values
            logging.warning("Start or end time is missing. Returning N/A.")
            return "N/A"
        if end_time < start_time:
            logging.warning("End time is before start time. Returning N/A.")
            return "N/A"
        duration = end_time - start_time
        minutes, seconds = divmod(duration.seconds, 60)
        return f"{minutes}m {seconds}s"
    except Exception as e:
        logging.error(f"Error computing duration: {e}", exc_info=True)
        return "N/A"

def get_workflow_run(github_token, repo_name, run_id):
    """Retrieves workflow run information and logs the process."""
    try:
        logging.info(f"Fetching workflow run {run_id} information...")
        headers = {key: value.format(github_token=github_token) for key, value in GITHUB_HEADERS_TEMPLATE.items()}
        url = GITHUB_WORKFLOW_RUN_URL.format(repo_name=repo_name, run_id=run_id)

        response = requests.get(url, headers=headers)
        logging.info(f"GitHub API request URL: {url}")
        logging.info(f"GitHub API response status code: {response.status_code}")

        response.raise_for_status()
        workflow_run = response.json()
        logging.info(f"Successfully fetched workflow run {run_id} information.")
        return workflow_run
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch workflow run: {e}", exc_info=True)
        sys.exit(1)

def get_workflow_jobs(github_token, repo_name, run_id, current_job_id):
    """Retrieves workflow job information, waits for other jobs to complete, and logs the process.
       Excludes the current job (notify-telegram) based on its ID.
    """
    try:
        logging.info("Fetching workflow job information...")
        headers = {key: value.format(github_token=github_token) for key, value in GITHUB_HEADERS_TEMPLATE.items()}
        url = GITHUB_WORKFLOW_JOBS_URL.format(repo_name=repo_name, run_id=run_id)

        attempts = 0
        while attempts < MAX_ATTEMPTS:
            response = requests.get(url, headers=headers)
            try:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            except requests.exceptions.HTTPError as e:
                logging.error(f"Error fetching job status: {e}")
                return None

            jobs_data = response.json()

            # List all job statuses
            logging.info("Current job statuses:")
            for job in jobs_data['jobs']:
                job_id = job.get('id')
                status = job.get('status')
                logging.info(f"  Job ID: {job_id}, Status: {status}")

            pending_jobs = [
                job for job in jobs_data['jobs']
                if job.get('id') != current_job_id and job.get('status') != 'completed'
            ]
            if not pending_jobs:
                logging.info("All other jobs have completed.")
                return jobs_data
            else:
                logging.info(f"Waiting for {len(pending_jobs)} job(s) to complete...")
                time.sleep(SLEEP_INTERVAL)
                attempts += 1
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch workflow jobs: {e}", exc_info=True)
        sys.exit(1)

def get_current_job_id(github_token, repo_name, run_id, job_name):
    """Retrieves the current job ID based on the job name, handling potential naming inconsistencies."""
    try:
        headers = {key: value.format(github_token=github_token) for key, value in GITHUB_HEADERS_TEMPLATE.items()}
        url = GITHUB_WORKFLOW_JOBS_URL.format(repo_name=repo_name, run_id=run_id)
        response = requests.get(url, headers=headers)
        try:
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.HTTPError as e:
            logging.error(f"Error fetching job status: {e}")
            return None
        
        jobs_data = response.json()
        
        # Find the job with the matching name, considering potential naming variations:
        # - Case-insensitive match
        # - Removing any leading/trailing whitespace
        # - Removing any special characters (e.g., "-", "_")
        # - Removing spaces, removing leading/trailing whitespaces
        for job in jobs_data['jobs']:
            job_name_in_api = job.get('name', '').strip().lower()
            job_name_in_api = ''.join(c for c in job_name_in_api if c.isalnum())  # Keep alphanumeric only
            job_name_in_workflow = job_name.strip().lower()
            job_name_in_workflow = ''.join(c for c in job_name_in_workflow if c.isalnum())

            if job_name_in_api == job_name_in_workflow:
                return job.get('id')
        
        logging.error(f"Job '{job_name}' not found in workflow run {run_id}.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch job ID: {e}", exc_info=True)
        sys.exit(1)

def calculate_total_duration(jobs, current_job_id):
    """Calculates the total duration of all jobs except the current one (using job ID)."""
    total_duration = timedelta(0)
    for job in jobs.get('jobs', []): # handles the jobs not being in the response.
        if job.get('id') == current_job_id:
            continue  # Skip current job

        if job.get('started_at') and job.get('completed_at'):
            try:
                start_time = datetime.strptime(job['started_at'], '%Y-%m-%dT%H:%M:%SZ')
                end_time = datetime.strptime(job['completed_at'], '%Y-%m-%dT%H:%M:%SZ')
                total_duration += (end_time - start_time)
            except (ValueError, TypeError) as e:
                logging.warning(f"Error parsing start/end times for job {job.get('name', 'Unknown')}: {e}")
                continue  # Skip this job if time parsing fails

    return total_duration

def get_status_icon(conclusion):
    """Returns a status icon based on the job conclusion."""
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

def get_workflow_status_emoji(conclusion):
    """Returns a workflow status emoji based on the conclusion."""
    if conclusion == "success":
        return "🟩"
    elif conclusion == "failure":
        return "🟥"
    elif conclusion == "cancelled":
        return "⬜"
    else:
        return "🟦"

def format_telegram_message(workflow, jobs, current_job_id):
    """Formats the Telegram message with detailed workflow and job information."""
    try:
        logging.info("Formatting the message for Telegram...")

        # Extract workflow information, using .get() to handle missing keys
        workflow_name = workflow.get('name', 'Unknown Workflow')
        run_number = workflow.get('run_number', '#')
        event_type = workflow.get('event', 'workflow_dispatch')
        event_url = workflow.get('html_url', '')
        workflow_conclusion = workflow.get('conclusion')
        
        try:
            created_at = datetime.strptime(workflow['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            updated_at = datetime.strptime(workflow['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
            duration = compute_duration(created_at, updated_at)
        except (KeyError, ValueError, TypeError) as e:
            logging.warning(f"Error calculating workflow duration: {e}")
            duration = "N/A"

        workflow_display_name = f"{workflow_name} #{run_number}"
        author_name = workflow.get('actor', {}).get('login', 'Unknown Author') # handle potential missing keys
        author_url = workflow.get('actor', {}).get('html_url', '') # handle potential missing keys
        workflow_status_emoji = get_workflow_status_emoji(workflow_conclusion)

        # Start building the message
        message = f"{workflow_status_emoji} *GITHUB ACTIONS NOTIFICATION*\n\n"
        message += f"🔄 _Event:_ `{event_type}` | ⚙️ _Workflow:_ [{workflow_display_name}]({event_url}) _completed in_ {duration}\n\n"

        # Add event details based on event type
        if event_type == "pull_request":
            pr = workflow.get("pull_requests", [{}])[0]
            pr_title = pr.get("title", "Unknown Pull Request")
            pr_url = pr.get("html_url", event_url)
            message += f"🔗 [Pull Request: {pr_title}]({pr_url})\n\n"
        elif event_type == "push":
            commit_message = workflow.get("head_commit", {}).get("message", "No commit message")
            commit_sha = workflow.get("head_commit", {}).get("id", "")
            commit_url = f"{workflow.get('repository', {}).get('html_url', '')}/commit/{commit_sha}" if commit_sha else ""
            message += f"📝 [Commit: {commit_message}]({commit_url})\n\n" if commit_url else f"📝 Commit: {commit_message}\n\n"
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
            repo_html_url = workflow.get('repository', {}).get('html_url', '')
            ref_url = f"{repo_html_url}/tree/{ref_name}" if ref_name and repo_html_url else ""
            message += f"🔗 [Created: {ref_type}]({ref_url}) {ref_name}\n\n" if ref_url else f"🔗 Created: {ref_type} {ref_name}\n\n"
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
            message += "🔗 [Event details]\n\n"  # Generic message for other events

        message += f"👤 _Author:_ [{author_name}]({author_url})\n\n"
        message += "_Job Details:_ \n\n"
        
        # Create two lists to store the job details for each column
        left_column = []
        right_column = []

        filtered_jobs = [job for job in jobs['jobs'] if job.get('id') != current_job_id] # filter by ID

        for i, job in enumerate(filtered_jobs):
            job_name = job.get('name', 'Unknown Job')
            job_url = job.get('html_url', '')
            try:
                started_at = datetime.strptime(job.get('started_at'), '%Y-%m-%dT%H:%M:%SZ') if job.get('started_at') else None
                completed_at = datetime.strptime(job.get('completed_at'), '%Y-%m-%dT%H:%M:%SZ') if job.get('completed_at') else None
                job_duration = compute_duration(started_at, completed_at)
            except (ValueError, TypeError) as e:
                logging.warning(f"Error parsing start/end times for job {job_name}: {e}")
                job_duration = "N/A"

            if not job_duration:
               if job.get('started_at'):
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

        # Calculate the maximum width of the left column
        max_left_width = max(len(detail) for detail in left_column) if left_column else 0

        # Define the format string for aligning the columns
        # Use 4 spaces (tabs) for right column alignment
        format_string = f"{{:<{max_left_width + 4}}} {{:>{max_left_width + 2}}}"

        # Get the maximum number of lines in either column
        max_lines = max(len(left_column), len(right_column))

        # Format the message with two columns
        for i in range(max_lines):
            left = left_column[i] if i < len(left_column) else ""
            right = right_column[i] if i < len(right_column) else ""
            message += format_string.format(left, right) + "\n\n"  # Add a newline after each row

        repo_url = workflow.get('repository', {}).get('html_url', '')
        repo_name = workflow.get('repository', {}).get('full_name', 'Unknown Repository')
        message += f"\n📦 _Repository:_ [{repo_name}]({repo_url})\n\n" # Added new line for better formatting

        logging.info("Message formatted successfully.")
        return message
    except Exception as e:
        logging.error(f"Error formatting Telegram message: {e}", exc_info=True)
        return "Error formatting message. See logs for details."

if __name__ == "__main__":
    try:
        logging.info("Starting Telegram notification action...")

        env = load_env_variables()
        check_telegram_connection(env['telegram_token'])
        check_github_access(env['github_token'], env['repo_name'])

        workflow_run = get_workflow_run(env['github_token'], env['repo_name'], env['run_id'])

        current_job_id = get_current_job_id(env['github_token'], env['repo_name'], env['run_id'], env['current_job_name'])
        logging.info(f"Current job id: {current_job_id}")

        workflow_jobs = get_workflow_jobs(env['github_token'], env['repo_name'], env['run_id'], current_job_id)
        message = format_telegram_message(workflow_run, workflow_jobs, current_job_id)
        send_telegram_message(env['telegram_token'], env['chat_id'], message)

        logging.info("Telegram notification action completed successfully.")
    except Exception as e:
        logging.error(f"Telegram notification action failed: {e}", exc_info=True)
        sys.exit(1)
