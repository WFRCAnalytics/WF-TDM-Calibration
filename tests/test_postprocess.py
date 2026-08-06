"""tdmcalib.postprocess.build_report_cache()/render_validation() -- the
automatic per-run report caching + quarto render after a successful run,
replacing the old preprocess toggle. Mocks shutil.which/subprocess.run
rather than requiring a real Quarto install or report/preprocess/ run."""
import subprocess

from tdmcalib import postprocess as pp


def test_build_report_cache_success(repo_root, monkeypatch):
    def fake_run(command, cwd, capture_output, text, timeout):
        assert command[:3] == [pp.sys.executable, "-m", "report.preprocess.build_cache"]
        assert command[-2:] == ["--run", "C50"]
        assert cwd == str(repo_root)
        return subprocess.CompletedProcess(command, returncode=0, stdout="[OK  ] modeled_tripgen: ok\n", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp.build_report_cache(repo_root, "C50")
    assert result["status"] == "success"


def test_build_report_cache_failed_on_nonzero_exit(repo_root, monkeypatch):
    def fake_run(command, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(command, returncode=1, stdout="[FAIL] modeled_tripgen: failed: boom\n", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp.build_report_cache(repo_root, "C50")
    assert result["status"] == "failed"
    assert "exited 1" in result["reason"]
    assert "boom" in result["stdout_tail"]


def test_build_report_cache_failed_on_timeout(repo_root, monkeypatch):
    def fake_run(command, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp.build_report_cache(repo_root, "C50")
    assert result["status"] == "failed"
    assert "timed out after 1800s" in result["reason"]


def test_render_validation_skipped_when_not_configured(repo_root):
    framework = {}  # no "postprocess" key at all
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "skipped"


def test_render_validation_skipped_when_disabled(repo_root):
    framework = {"postprocess": {"render_validation": False}}
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "skipped"


def test_render_validation_failed_when_quarto_not_on_path(repo_root, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda exe: None)
    framework = {"postprocess": {"render_validation": True, "quarto_exe": "quarto"}}
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "failed"
    assert "not found on PATH" in result["reason"]


def test_render_validation_success(repo_root, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda exe: "/usr/bin/quarto")

    def fake_run(command, cwd, capture_output, text, timeout):
        assert command[:2] == ["quarto", "render"]
        assert cwd == str(repo_root)
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    framework = {"postprocess": {"render_validation": True}}
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "success"


def test_render_validation_failed_on_nonzero_exit(repo_root, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda exe: "/usr/bin/quarto")

    def fake_run(command, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    framework = {"postprocess": {"render_validation": True}}
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "failed"
    assert "exited 1" in result["reason"]
    assert "boom" in result["stderr_tail"]


def test_render_validation_failed_on_timeout(repo_root, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda exe: "/usr/bin/quarto")

    def fake_run(command, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    framework = {"postprocess": {"render_validation": True, "timeout_seconds": 5}}
    result = pp.render_validation(repo_root, framework)
    assert result["status"] == "failed"
    assert "timed out after 5s" in result["reason"]
