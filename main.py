import os
import requests
import logging
from datetime import datetime
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for GitHub icon URL
github_icon_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"

# Global function to load environment variables
def load_env_variables():
    try:
        env_vars = {
            'telegram_token': os.getenv('TELEGRAM_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
            'github_token': os.getenv('GITHUB_TOKEN'),
            'repo_name': os.getenv('GITHUB_REPOSITORY'),
            'run_id': os.getenv('GITHUB_RUN_ID'),
            'current_job_name': os.getenv('GITHUB_JOB')  # Get the current job name
        }
        
        # Log environment variables for debugging purposes (excluding sensitive data)
        logging.info(f"Loaded environment variables: REPO_NAME={env_vars['repo_name']}, RUN_ID={env_vars['run_id']}, CURRENT_JOB_NAME={env_vars['current_job_name']}")
        
        return env_vars
    except Exception as e:
        logging.error(f"Failed to load environment variables: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to check connection to Telegram
def check_telegram_connection(telegram_token):
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
    try:
        logging.info("Checking GitHub API access...")
        
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # API URL to check access to repository
        url = f'https://api.github.com/repos/{repo_name}'
        
        # Make request to GitHub API
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
    try:
        if end_time < start_time:
            logging.error("End time is earlier than start time")
            return "Invalid time"

        duration = end_time - start_time
        minutes, seconds = divmod(duration.seconds, 60)
        return f"{minutes}m {seconds}s"
    except Exception as e:
        logging.error(f"Error computing duration: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to calculate total duration from jobs, excluding the current job (Telegram notification job)
def calculate_total_duration(jobs, current_job_name):
    try:
        total_duration = 0
        for job in jobs['jobs']:
            # Skip the current job (Telegram notification job)
            if job['name'] == current_job_name:
                logging.info(f"Skipping current job '{current_job_name}' in duration calculation.")
                continue

            # Ensure job has both 'started_at' and 'completed_at', and they are not None
            if job.get('started_at') and job.get('completed_at'):
                start_time = datetime.strptime(job['started_at'], '%Y-%m-%dT%H:%M:%SZ')
                end_time = datetime.strptime(job['completed_at'], '%Y-%m-%dT%H:%M:%SZ')
                duration = (end_time - start_time).total_seconds()
                total_duration += duration
            else:
                logging.warning(f"Job {job['name']} has incomplete timing information, skipping...")

        return total_duration
    except Exception as e:
        logging.error(f"Error calculating total duration: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to get detailed information about a workflow run based on run_id
def get_workflow_run(github_token, repo_name, run_id):
    try:
        logging.info(f"Fetching workflow run {run_id} information...")

        # Set headers for authentication
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # API URL to fetch a run
        url = f'https://api.github.com/repos/{repo_name}/actions/runs/{run_id}'

        # Make the request to GitHub API
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error if the request failed
        workflow_run = response.json()  # Parse the response as JSON

        logging.info(f"Successfully fetched workflow run {run_id} information.")
        return workflow_run
    except Exception as e:
        logging.error(f"Failed to fetch workflow run: {str(e)}", exc_info=True)
        sys.exit(1)

# Fetch job information from GitHub API
def get_workflow_jobs(github_token, repo_name, run_id):
    try:
        logging.info("Fetching workflow job information from GitHub API...")
        
        # Set headers for authentication
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # API URL to fetch jobs for a workflow run
        url = f'https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/jobs'

        # Make the request to GitHub API
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error if the request failed
        jobs = response.json()  # Parse the response as JSON

        logging.info("Successfully fetched workflow and job information.")
        return jobs
    except Exception as e:
        logging.error(f"Failed to fetch workflow jobs: {str(e)}", exc_info=True)
        sys.exit(1)

# Map job conclusion to corresponding status icon
def get_status_icon(conclusion):
    try:
        status_icons = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "skipped": "⏭️",
            "in_progress": "⏳",
            "timed_out": "⏰",
            "neutral": "⚪",
            "action_required": "⚠️"
        }
        return status_icons.get(conclusion, "❓")
    except Exception as e:
        logging.error(f"Error mapping status icon: {str(e)}", exc_info=True)
        sys.exit(1)

# Function to format the message for Telegram
def format_telegram_message(workflow, jobs, current_job_name):
    try:
        logging.info("Formatting the message for Telegram...")

        # Base information
        workflow_name = workflow.get('name', 'Unknown Workflow')
        run_number = str(workflow.get('run_number', '#'))
        event_type = workflow.get('event', 'workflow_dispatch')
        event_url = workflow.get('html_url', '')
        duration = compute_duration(datetime.strptime(workflow['created_at'], '%Y-%m-%dT%H:%M:%SZ'), 
                                    datetime.strptime(workflow['updated_at'], '%Y-%m-%dT%H:%M:%SZ'))

        # Combine workflow_name and run_number
        workflow_display_name = f"{workflow_name} #{run_number}"

        # Author information
        author_name = workflow['actor']['login']
        author_url = workflow['actor']['html_url']

        # Message header
        message = f"🔔 *Github Actions Notification*\n\n"

        # Event information with dynamic workflow name and duration (inline code for event_type and italic for labels)
        message += f"🔄 _Event:_ `{event_type}` | ⚙️ _Workflow:_ [{workflow_display_name}]({event_url}) _completed in_ {duration}\n\n"

        # Author information (italic for "Author")
        message += f"👤 _Author:_ [{author_name}]({author_url})\n\n"

        # Job details with icons and durations (italic for "Job Details")
        message += "_Job Details:_ \n\n"
        left_column = []
        right_column = []
        for i, job in enumerate(jobs['jobs']):
            if job['name'] == current_job_name:
                continue
            job_name = job['name']
            job_url = job['html_url']
            job_duration = compute_duration(datetime.strptime(job['started_at'], '%Y-%m-%dT%H:%M:%SZ'), 
                                            datetime.strptime(job['completed_at'], '%Y-%m-%dT%H:%M:%SZ'))
            job_conclusion = job['conclusion']
            job_icon = get_status_icon(job_conclusion)

            job_detail = f"{job_icon} [{job_name}]({job_url}) ({job_duration})"
            if i % 2 == 0:
                left_column.append(job_detail)
            else:
                right_column.append(job_detail)

        # Format left and right columns with more space between them
        max_lines = max(len(left_column), len(right_column))
        for i in range(max_lines):
            left = left_column[i] if i < len(left_column) else ""
            right = right_column[i] if i < len(right_column) else ""
            # Add more spacing (e.g., 4 tabs) between the columns
            message += f"{left}\t\t\t\t\t\t\t\t{right}\n\n"

        # Repository information (italic for "Repository")
        repo_url = workflow['repository']['html_url']
        repo_name = workflow['repository']['full_name']
        message += f"📦 _Repository:_ [{repo_name}]({repo_url})"

        logging.info("Message formatted successfully.")
        return message
    except Exception as e:
        logging.error(f"Error formatting the message: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        logging.info("Starting the Telegram notification action...")

        # Load environment variables
        env = load_env_variables()

        # Check connections to Telegram and GitHub API
        check_telegram_connection(env['telegram_token'])
        repo_info = check_github_access(env['github_token'], env['repo_name'])

        # Fetch workflow run and job details
        logging.info("Fetching workflow run and job details...")
        workflow_run = get_workflow_run(env['github_token'], env['repo_name'], env['run_id'])
        workflow_jobs = get_workflow_jobs(env['github_token'], env['repo_name'], env['run_id'])

        # Format the message
        logging.info("Formatting the message...")
        message = format_telegram_message(workflow_run, workflow_jobs, env['current_job_name'])

        # Send the message to Telegram
        logging.info("Sending message to Telegram...")
        send_telegram_message(env['telegram_token'], env['chat_id'], message)
        
        logging.info("Action completed successfully.")
    except Exception as e:
        logging.error(f"Action failed: {str(e)}", exc_info=True)
        sys.exit(1)
