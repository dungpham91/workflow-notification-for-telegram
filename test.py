import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from main import compute_duration, get_status_icon, send_telegram_message, load_env_variables

class TestSendNotification(unittest.TestCase):

    # Test function to check compute_duration
    def test_compute_duration(self):
        start_time = datetime(2023, 9, 1, 12, 0, 0)
        end_time = datetime(2023, 9, 1, 12, 30, 30)
        duration = compute_duration(start_time, end_time)
        self.assertEqual(duration, "30m 30s")

    # Test for invalid time
    def test_compute_duration_invalid(self):
        start_time = datetime(2023, 9, 1, 12, 0, 0)
        end_time = datetime(2023, 9, 1, 11, 30, 30)  # Invalid time
        duration = compute_duration(start_time, end_time)
        self.assertEqual(duration, "Invalid time")

    # Test function to check get_status_icon
    def test_get_status_icon(self):
        self.assertEqual(get_status_icon("success"), "✅")
        self.assertEqual(get_status_icon("failure"), "❌")
        self.assertEqual(get_status_icon("cancelled"), "🚫")
        self.assertEqual(get_status_icon("skipped"), "⏭️")
        self.assertEqual(get_status_icon("timed_out"), "⏰")
        self.assertEqual(get_status_icon("neutral"), "⚪")
        self.assertEqual(get_status_icon("action_required"), "⚠️")
        self.assertEqual(get_status_icon("unknown"), "❓")

    # Test function to mock the Telegram message sending
    @patch('send_notification.requests.post')
    def test_send_telegram_message(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        send_telegram_message("fake_token", "fake_chat_id", "Test message")
        
        mock_post.assert_called_once_with(
            'https://api.telegram.org/botfake_token/sendMessage',
            json={
                'chat_id': 'fake_chat_id',
                'text': 'Test message',
                'parse_mode': 'Markdown'
            }
        )

    # Test loading environment variables
    @patch.dict('os.environ', {
        'TELEGRAM_TOKEN': 'fake_telegram_token',
        'TELEGRAM_CHAT_ID': 'fake_chat_id',
        'GITHUB_TOKEN': 'fake_github_token',
        'GITHUB_REPOSITORY': 'fake_repo',
        'GITHUB_RUN_ID': '1234'
    })
    def test_load_env_variables(self):
        env_vars = load_env_variables()
        self.assertEqual(env_vars['telegram_token'], 'fake_telegram_token')
        self.assertEqual(env_vars['chat_id'], 'fake_chat_id')
        self.assertEqual(env_vars['github_token'], 'fake_github_token')
        self.assertEqual(env_vars['repo_name'], 'fake_repo')
        self.assertEqual(env_vars['run_id'], '1234')

if __name__ == "__main__":
    unittest.main()
