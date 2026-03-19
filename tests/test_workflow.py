"""
tests/test_workflow.py — GitHub Actions workflow 파일 검증
"""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".github", "workflows", "main.yml"
)

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
]


class TestWorkflowFile:
    """6.7 test_workflow_file — main.yml YAML 파싱으로 cron 및 env 블록 검증"""

    @pytest.fixture(scope="class")
    def workflow(self):
        """main.yml을 파싱하여 반환."""
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_workflow_file_exists(self):
        """main.yml 파일이 존재해야 한다."""
        assert os.path.isfile(WORKFLOW_PATH), f"workflow 파일이 없습니다: {WORKFLOW_PATH}"

    def test_workflow_cron_expression(self, workflow):
        """cron 표현식 '0 1 * * *'이 포함되어야 한다."""
        # YAML에서 'on'은 Python 예약어라 True로 파싱될 수 있음
        on_block = workflow.get("on") or workflow.get(True) or {}
        schedules = on_block.get("schedule", []) if isinstance(on_block, dict) else []
        cron_expressions = [s.get("cron") for s in schedules if isinstance(s, dict)]
        assert "0 1 * * *" in cron_expressions, (
            f"cron '0 1 * * *'이 없습니다. 현재 cron: {cron_expressions}"
        )

    def test_workflow_env_contains_required_vars(self, workflow):
        """env 블록에 필수 환경 변수가 모두 포함되어야 한다."""
        jobs = workflow.get("jobs", {})
        all_env_keys = set()

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                env = step.get("env", {})
                all_env_keys.update(env.keys())

        for var in REQUIRED_ENV_VARS:
            assert var in all_env_keys, (
                f"필수 환경 변수 '{var}'가 workflow env 블록에 없습니다."
            )

    def test_workflow_has_python_setup(self, workflow):
        """Python 설치 스텝이 포함되어야 한다."""
        jobs = workflow.get("jobs", {})
        found_python_setup = False

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "setup-python" in uses:
                    found_python_setup = True
                    break

        assert found_python_setup, "Python 설치 스텝(setup-python)이 없습니다."

    def test_workflow_has_checkout_step(self, workflow):
        """checkout 스텝이 포함되어야 한다."""
        jobs = workflow.get("jobs", {})
        found_checkout = False

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "checkout" in uses:
                    found_checkout = True
                    break

        assert found_checkout, "checkout 스텝이 없습니다."
