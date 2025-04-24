from django.test import TestCase
from unittest.mock import patch
from hrms_app.tasks import send_reminder_email

class SendReminderEmailTaskTest(TestCase):
    @patch('django.core.mail.EmailMessage')
    def test_send_reminder_email(self, mock_email_class):
        mock_email_instance = mock_email_class.return_value
        send_reminder_email()
        mock_email_class.assert_called_once()
        mock_email_instance.send.assert_called_once()
