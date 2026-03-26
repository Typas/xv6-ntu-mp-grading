import unittest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock

# Import the scripts to test
# Add tools directory to sys.path
import sys
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(repo_root, "tools"))

import trigger_grading
import grading_crawler

class TestGradingLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mp = "mp0"
        self.result_dir = os.path.join(self.test_dir, self.mp, "result")
        os.makedirs(self.result_dir, exist_ok=True)
        self.targets_file = os.path.join(self.result_dir, "grading_targets.json")
        self.payload_dir = os.path.join(self.test_dir, self.mp, "payload")
        os.makedirs(self.payload_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("trigger_grading.run_cmd")
    @patch("trigger_grading.process_repo")
    def test_trigger_grading_push_detection(self, mock_process, mock_run_cmd):
        # Case 1: No push occurred
        mock_process.return_value = ("sha123", False)
        
        with patch.object(sys, 'argv', ["trigger_grading.py", "--mp", self.mp, "--repo", "owner/repo", "--grading-dir", self.test_dir, "--force-push"]):
            trigger_grading.main()
            
        push_signal = os.path.join(self.result_dir, ".push_occurred")
        self.assertFalse(os.path.exists(push_signal), "Signal file should NOT exist when no push happened")

        # Case 2: Push occurred
        mock_process.return_value = ("sha456", True)
        with patch.object(sys, 'argv', ["trigger_grading.py", "--mp", self.mp, "--repo", "owner/repo", "--grading-dir", self.test_dir, "--force-push"]):
            trigger_grading.main()
            
        self.assertTrue(os.path.exists(push_signal), "Signal file SHOULD exist when push happened")
        with open(push_signal, "r") as f:
            self.assertEqual(f.read(), "true")

    @patch("trigger_grading.run_cmd")
    @patch("trigger_grading.process_repo")
    def test_trigger_grading_exclude_repo(self, mock_process, mock_run_cmd):
        # Prepare a student list file
        students_file = os.path.join(self.test_dir, "students.json")
        student_list = ["owner/repo1", "owner/repo2", "owner/repo3"]
        with open(students_file, "w") as f:
            json.dump(student_list, f)
            
        mock_process.return_value = ("sha123", False)
        
        # Test excluding repo2
        with patch.object(sys, 'argv', ["trigger_grading.py", "--mp", self.mp, "--students", students_file, "--grading-dir", self.test_dir, "--exclude-repo", "owner/repo2"]):
            trigger_grading.main()
            
        with open(self.targets_file, "r") as f:
            targets = json.load(f)
            repos = [t["repo"] for t in targets]
            self.assertIn("owner/repo1", repos)
            self.assertNotIn("owner/repo2", repos)
            self.assertIn("owner/repo3", repos)
            self.assertEqual(len(repos), 2)

    @patch("grading_crawler.requests.get")
    def test_crawler_incremental_and_force(self, mock_get):
        # Prepare targets
        targets = [{"repo": "owner/repo1", "commit_sha": "sha1"}, {"repo": "owner/repo2", "commit_sha": "sha2"}]
        with open(self.targets_file, "w") as f:
            json.dump(targets, f)
            
        # Prepare existing results (cache)
        cache_file = os.path.join(self.result_dir, "final_grades.json")
        existing_results = [
            {"repo": "owner/repo1", "score": 100, "status": "Success", "run_url": "http://url1"}
        ]
        with open(cache_file, "w") as f:
            json.dump(existing_results, f)

        output_file = os.path.join(self.result_dir, "output.json")

        # Mock API response for repo2 (repo1 should be skipped)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Mocking repo data for visibility check
        mock_resp.json.side_effect = [
            {"private": True}, # Repo data for repo2
            {"workflow_runs": [{"path": ".github/workflows/grading.yml", "status": "completed", "conclusion": "success", "html_url": "http://url2", "artifacts_url": "http://art2", "updated_at": "2026-01-01T00:00:00Z"}]}, # Runs for repo2
        ]
        mock_get.return_value = mock_resp

        # Mock download_artifact and parse_report_from_zip
        with patch("grading_crawler.download_artifact", return_value=b"zipcontent"), \
             patch("grading_crawler.parse_report_from_zip", return_value={"scores": {"final_score": 90}}):
            
            # Run 1: Normal Incremental (should skip repo1)
            with patch.object(sys, 'argv', ["grading_crawler.py", "--targets", self.targets_file, "--output", output_file, "--cache", cache_file]):
                grading_crawler.main()
            
            with open(output_file, "r") as f:
                results = json.load(f)
                repos = [r["repo"] for r in results]
                self.assertIn("owner/repo1", repos)
                self.assertIn("owner/repo2", repos)
                # repo1 should have original score 100, repo2 should have 90
                for r in results:
                    if r["repo"] == "owner/repo1": self.assertEqual(r["score"], 100)
                    if r["repo"] == "owner/repo2": self.assertEqual(r["score"], 90)
            
            # Run 2: Force Fetch (should refetch repo1)
            # Reset mock for repo1 refetch
            mock_get.reset_mock()
            mock_resp.json.side_effect = [
                {"private": True}, # Repo data for repo1
                {"workflow_runs": [{"path": ".github/workflows/grading.yml", "status": "completed", "conclusion": "success", "html_url": "http://url1-new", "artifacts_url": "http://art1-new", "updated_at": "2026-01-01T00:00:00Z"}]}, # Runs for repo1
                {"private": True}, # Repo data for repo2
                {"workflow_runs": [{"path": ".github/workflows/grading.yml", "status": "completed", "conclusion": "success", "html_url": "http://url2", "artifacts_url": "http://art2", "updated_at": "2026-01-01T00:00:00Z"}]}, # Runs for repo2
            ]
            with patch.object(sys, 'argv', ["grading_crawler.py", "--targets", self.targets_file, "--output", output_file, "--cache", cache_file, "--force-fetch"]):
                # Mock parse_report_from_zip to return a new score for repo1
                with patch("grading_crawler.parse_report_from_zip", side_effect=[{"scores": {"final_score": 85}}, {"scores": {"final_score": 90}}]):
                    grading_crawler.main()
            
            with open(output_file, "r") as f:
                results = json.load(f)
                for r in results:
                    if r["repo"] == "owner/repo1":
                        self.assertEqual(r["score"], 85, f"Repo1 score should be 85, got {r['score']}. Status: {r.get('status')}")

if __name__ == "__main__":
    unittest.main()
