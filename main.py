import os
import requests
import logging
from datetime import datetime
from github import Github
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global function to load environment variables
def load_env_variables():
    try:
        env_vars = {
            'telegram_token': os.getenv('TELEGRAM_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
            'github_token': os.getenv('GITHUB_TOKEN'),
            'repo_name': os.getenv('GITHUB_REPOSITORY'),
            'run_id': os.getenv('GITHUB_RUN_ID')
        }
        
        # Log environment variables for debugging purposes (excluding sensitive data)
        logging.info(f"Loaded environment variables: REPO_NAME={env_vars['repo_name']}, RUN_ID={env_vars['run_id']}")
        
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
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        logging.info(f"GitHub API access successful. Repo name: {repo.full_name}")
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

# Fetch job information from GitHub API
def get_workflow_jobs(github_token, repo_name, run_id):
    try:
        logging.info("Fetching workflow job information from GitHub API...")
        
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        run = repo.get_workflow_run(run_id)
        jobs = run.get_jobs()

        logging.info("Successfully fetched workflow and job information.")
        return run, jobs
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
            "timed_out": "⏰",
            "neutral": "⚪",
            "action_required": "⚠️"
        }
        return status_icons.get(conclusion, "❓")
    except Exception as e:
        logging.error(f"Error mapping status icon: {str(e)}", exc_info=True)
        sys.exit(1)

# Format the message to be sent to Telegram
def format_telegram_message(workflow, jobs):
    try:
        logging.info("Formatting the message for Telegram...")
        
        message = f"🔔 *{workflow.name}* \n\n"
        message += f"💼 *Status*: {'Success' if workflow.conclusion == 'success' else 'Failure'}\n"
        message += f"🕒 *Completed in*: {compute_duration(workflow.created_at, workflow.updated_at)}\n\n"
        message += "*Job Details:*\n"

        for job in jobs:
            job_icon = get_status_icon(job.conclusion)
            job_duration = compute_duration(job.started_at, job.completed_at)
            message += f"{job_icon} `{job.name}` ({job_duration})\n"

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
        check_github_access(env['github_token'], env['repo_name'])

        # Fetch workflow and job details
        logging.info("Fetching workflow and job details...")
        workflow_run, workflow_jobs = get_workflow_jobs(env['github_token'], env['repo_name'], env['run_id'])

        # Format the message
        logging.info("Formatting the message...")
        message = format_telegram_message(workflow_run, workflow_jobs)

        # Send the message to Telegram
        logging.info("Sending message to Telegram...")
        send_telegram_message(env['telegram_token'], env['chat_id'], message)
        
        logging.info("Action completed successfully.")
    except Exception as e:
        logging.error(f"Action failed: {str(e)}", exc_info=True)
        sys.exit(1)
