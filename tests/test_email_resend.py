import json
import unittest
import urllib.error
from unittest import mock

from app.services import email_service

BASIS_CONFIG = {
    'RESEND_API_KEY': 're_test_key',
    'VERZENDER_EMAIL': 'info@restaurant.nl',
    'VERZENDER_WACHTWOORD': '',
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': 587,
}

BERICHT = {
    'from': 'info@restaurant.nl',
    'to': 'gast@example.com',
    'subject': 'Bevestiging',
    'tekst': 'Hallo',
}


class ResendVersturenTests(unittest.TestCase):
    def test_verstuurt_via_resend_met_bearer_en_json(self):
        with mock.patch.object(email_service.urllib.request, 'urlopen') as urlopen:
            email_service.async_send_email(BASIS_CONFIG, BERICHT, 'gast@example.com', 'res-1')

        verzoek = urlopen.call_args.args[0]
        self.assertEqual(verzoek.full_url, email_service.RESEND_URL)
        self.assertEqual(verzoek.get_method(), 'POST')
        self.assertEqual(verzoek.get_header('Authorization'), 'Bearer re_test_key')
        self.assertEqual(json.loads(verzoek.data.decode('utf-8')), {
            'from': 'info@restaurant.nl',
            'to': ['gast@example.com'],
            'subject': 'Bevestiging',
            'text': 'Hallo',
        })

    def test_gebruikt_geen_smtp_als_resend_key_gezet_is(self):
        with mock.patch.object(email_service.urllib.request, 'urlopen'), \
                mock.patch.object(email_service.smtplib, 'SMTP') as smtp:
            email_service.async_send_email(BASIS_CONFIG, BERICHT, 'gast@example.com', 'res-1')
        smtp.assert_not_called()

    def test_http_fout_wordt_gelogd_met_status(self):
        fout = urllib.error.HTTPError(email_service.RESEND_URL, 403, 'Forbidden', None, None)
        with mock.patch.object(email_service.urllib.request, 'urlopen', side_effect=fout), \
                self.assertLogs('app.services.email_service', level='ERROR') as logs:
            email_service.async_send_email(BASIS_CONFIG, BERICHT, 'gast@example.com', 'res-1')
        self.assertIn('[MAIL_FAILED] reservering_id=res-1 error_type=HTTPError status=403', logs.output[0])

    def test_zonder_resend_key_en_zonder_wachtwoord_is_het_simulatie(self):
        config = dict(BASIS_CONFIG, RESEND_API_KEY='')
        with mock.patch.object(email_service.urllib.request, 'urlopen') as urlopen, \
                self.assertLogs('app.services.email_service', level='INFO') as logs:
            email_service.async_send_email(config, BERICHT, 'gast@example.com', 'res-1')
        urlopen.assert_not_called()
        self.assertIn('[MAIL_SIMULATIE]', logs.output[0])


if __name__ == '__main__':
    unittest.main()
