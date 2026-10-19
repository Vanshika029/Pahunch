import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main


class PahunchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        main.DB_PATH = Path(cls.temp_dir.name) / "test.db"
        main._scheme_cache.clear()
        main._request_counts.clear()
        main.initialize_database()
        cls.client_context = TestClient(main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.temp_dir.cleanup()

    def setUp(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "demo@pahunch.in", "password": "Pahunch123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_protected_routes_require_authentication(self):
        response = self.client.get("/api/v1/schemes")
        self.assertEqual(response.status_code, 401)

    def test_schemes_are_searchable_and_eligibility_is_profile_based(self):
        response = self.client.get("/api/v1/schemes?q=health", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], "ayushman-bharat")
        self.assertTrue(response.json()["items"][0]["eligible"])

    def test_application_tracking_and_duplicate_protection(self):
        response = self.client.post(
            "/api/v1/applications",
            headers=self.headers,
            json={"scheme_id": "pm-kisan", "notes": "Test application"},
        )
        self.assertEqual(response.status_code, 201)
        application = response.json()
        self.assertTrue(application["reference_number"].startswith("PAH-"))
        self.assertEqual(application["timeline"][0]["status"], "submitted")

        duplicate = self.client.post(
            "/api/v1/applications", headers=self.headers, json={"scheme_id": "pm-kisan"}
        )
        self.assertEqual(duplicate.status_code, 409)

        withdrawn = self.client.patch(
            f"/api/v1/applications/{application['id']}", headers=self.headers
        )
        self.assertEqual(withdrawn.status_code, 200)
        self.assertEqual(withdrawn.json()["status"], "withdrawn")

    def test_registration_and_profile_update(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "new-citizen@example.com",
                "password": "A-secure-demo-pass",
                "full_name": "New Citizen",
            },
        )
        self.assertEqual(response.status_code, 201)
        new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        profile = self.client.put(
            "/api/v1/profile",
            headers=new_headers,
            json={
                "age": 28,
                "annual_income": 150000,
                "state": "Uttar Pradesh",
                "category": "General",
                "gender": "female",
            },
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["age"], 28)

    def test_assistant_returns_transparent_guidance(self):
        response = self.client.post(
            "/api/v1/assistant/chat",
            headers=self.headers,
            json={"message": "Which schemes might I be eligible for?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_mode"], "rules-based demo")
        self.assertTrue(response.json()["scheme_ids"])

    def test_postgres_adapter_uses_postgres_placeholders_and_case_insensitive_search(self):
        class RecordingConnection:
            def execute(self, statement, parameters):
                return statement, parameters

        connection = main.DatabaseConnection(RecordingConnection(), postgres=True)
        statement, parameters = connection.execute(
            "SELECT * FROM schemes WHERE name LIKE ? AND category = ?",
            ("%health%", "Healthcare"),
        )
        self.assertEqual(statement, "SELECT * FROM schemes WHERE name ILIKE %s AND category = %s")
        self.assertEqual(parameters, ("%health%", "Healthcare"))

    def test_hosted_database_refuses_development_jwt_secret(self):
        database_url, jwt_secret = main.DATABASE_URL, main.JWT_SECRET
        try:
            main.DATABASE_URL = "postgresql://unreachable/test"
            main.JWT_SECRET = "development-only-change-me"
            with self.assertRaisesRegex(RuntimeError, "PAHUNCH_JWT_SECRET"):
                main.initialize_database()
        finally:
            main.DATABASE_URL, main.JWT_SECRET = database_url, jwt_secret


if __name__ == "__main__":
    unittest.main()
