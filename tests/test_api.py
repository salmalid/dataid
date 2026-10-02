import os
os.environ["DATAID_LLM_PROVIDER"] = "none"

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.api.main import app, _load_bundle
from backend.core import config, store


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in {"DB_PATH": root / "test.db", "UPLOADS_DIR": root,
                            "REQUIRE_API_KEY": False, "ADMIN_TOKEN": ""}.items():
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_project_upload_and_failed_replacement_preserves_dataset(self):
        response = self.client.post("/api/projects", json={"name": "Upload test"})
        self.assertEqual(response.status_code, 201)
        project_id = response.json()["id"]
        url = f"/api/projects/{project_id}/dataset"
        csv = "amount,age,label\n" + "\n".join(f"{i},{20+i%15},{i%2}" for i in range(100))
        response = self.client.post(url, files={"file": ("sample.csv", csv, "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        path = store.get_project(project_id)["dataset_path"]
        failed = self.client.post(url, files={"file": ("broken.csv", "", "text/csv")})
        self.assertEqual(failed.status_code, 400)
        self.assertTrue(Path(path).exists())
        self.assertEqual(store.get_project(project_id)["dataset_path"], path)
        preview = self.client.get(url + "/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["total_rows"], 100)

    def test_api_keys_scopes_revocation_and_browser_session(self):
        config.REQUIRE_API_KEY = True
        self.assertEqual(self.client.get("/api/projects").status_code, 401)
        key = store.create_api_key("read only", ["read"])
        headers = {"Authorization": "Bearer " + key["token"]}
        self.assertEqual(self.client.get("/api/projects", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/projects", json={"name": "denied"}, headers=headers).status_code, 403)
        self.assertIsNotNone(store.list_api_keys()[0]["last_used_at"])
        self.assertEqual(self.client.post("/api/session", json={"token": key["token"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/projects").status_code, 200)
        store.revoke_api_key(key["id"])
        self.assertEqual(self.client.get("/api/projects").status_code, 401)
        config.ADMIN_TOKEN = "test-bootstrap-only"
        self.assertEqual(self.client.post("/api/session", json={"token": config.ADMIN_TOKEN}).status_code, 200)
        self.assertEqual(self.client.post("/api/projects", json={"name": "allowed"}).status_code, 201)
        self.client.delete("/api/session")
        self.assertEqual(self.client.get("/api/projects").status_code, 401)

    def test_empty_scopes_grant_no_permissions(self):
        key = store.create_api_key("empty", [])
        self.assertEqual(store.authenticate_api_key(key["token"])["scopes"], [])
        self.assertEqual(self.client.get("/api/projects", headers={"Authorization": "Bearer " + key["token"]}).status_code, 403)

    def test_restart_marks_interrupted_runs_failed(self):
        project = store.create_project("interrupted", "")
        run = store.create_run(project["id"], "label", None, False)
        store.mark_run_running(run["id"])
        store.recover_interrupted_runs()
        recovered = store.get_run(run["id"])
        self.assertEqual(recovered["status"], "failed")
        self.assertIn("Backend stopped", recovered["error"])

    def test_executor_failure_clears_active_registry(self):
        from backend.api import runner
        project = store.create_project("bad run", "")
        run = store.create_run(project["id"], "label", None, False)
        with patch.object(runner._EXECUTOR, "submit", side_effect=lambda fn: fn()):
            runner.submit(project, run, "label", None, False, [])
        self.assertFalse(runner.is_active(run["id"]))
        self.assertEqual(store.get_run(run["id"])["status"], "failed")

    def test_production_promotion_controls_served_bundle(self):
        project = store.create_project("models", "")
        paths = []
        runs = []
        for i in range(2):
            run = store.create_run(project["id"], "label", None, False)
            path = Path(self.temp.name) / f"model-{i}.joblib"
            import joblib
            joblib.dump({"version": i}, path)
            store.finish_run(run["id"], {"status": "success", "artifacts": {"model_bundle": str(path)}})
            paths.append(path)
            runs.append(run)
        self.assertEqual(_load_bundle(project["id"])[0]["version"], 1)
        entry = next(m for m in store.list_registry(project["id"]) if m["run_id"] == runs[0]["id"])
        store.promote_model(entry["id"], "production")
        self.assertEqual(_load_bundle(project["id"])[0]["version"], 0)


if __name__ == "__main__":
    unittest.main()
