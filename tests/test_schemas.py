import unittest
from datetime import date, time

from pydantic import ValidationError

from app.schemas import AIReserveringExtractieSchema, ReserveringSchema


class ReserveringSchemaTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "naam": "Ada Lovelace",
            "email": "ada@example.com",
            "telefoon": "0612345678",
            "datum": "2026-10-25",
            "tijd": "18:30",
            "aantal": 2,
            "privacy_akkoord": True,
        }

    def test_rejects_invalid_email(self):
        payload = self.valid_payload()
        payload["email"] = "geen-geldig-adres"

        with self.assertRaises(ValidationError):
            ReserveringSchema.model_validate(payload)

    def test_person_count_must_be_between_one_and_twenty(self):
        for count in (0, 21):
            with self.subTest(count=count):
                payload = self.valid_payload()
                payload["aantal"] = count

                with self.assertRaises(ValidationError):
                    ReserveringSchema.model_validate(payload)

    def test_accepts_person_count_alias(self):
        payload = self.valid_payload()
        payload["aantal_personen"] = payload.pop("aantal")

        reservation = ReserveringSchema.model_validate(payload)

        self.assertEqual(reservation.aantal, 2)
        self.assertEqual(reservation.model_dump(mode="json")["aantal"], 2)

    def test_forbids_extra_fields(self):
        payload = self.valid_payload()
        payload["debug"] = True

        with self.assertRaises(ValidationError):
            ReserveringSchema.model_validate(payload)

    def test_parses_iso_date_and_time_to_native_types(self):
        reservation = ReserveringSchema.model_validate(self.valid_payload())

        self.assertEqual(reservation.datum, date(2026, 10, 25))
        self.assertEqual(reservation.tijd, time(18, 30))
        self.assertEqual(reservation.model_dump(mode="json")["datum"], "2026-10-25")
        self.assertEqual(reservation.model_dump(mode="json")["tijd"], "18:30")

    def test_rejects_invalid_calendar_date_and_time(self):
        for field, value in (("datum", "2026-02-30"), ("tijd", "24:00"), ("tijd", "18:30:00")):
            with self.subTest(field=field, value=value):
                payload = self.valid_payload()
                payload[field] = value

                with self.assertRaises(ValidationError):
                    ReserveringSchema.model_validate(payload)

    def test_dto_is_frozen(self):
        reservation = ReserveringSchema.model_validate(self.valid_payload())

        with self.assertRaises(ValidationError):
            reservation.naam = "Changed Name"

    def test_ai_extraction_optional_fields_have_no_fallback_values(self):
        extraction = AIReserveringExtractieSchema()

        self.assertIsNone(extraction.naam)
        self.assertIsNone(extraction.email)
        self.assertIsNone(extraction.aantal)


if __name__ == "__main__":
    unittest.main()