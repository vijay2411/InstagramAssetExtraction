import pytest
from app.storage.job_store import JobState, JobStatus, InMemoryJobStore

def test_create_job_returns_id_and_state():
    store = InMemoryJobStore()
    job = store.create(url="https://example.com/reel/1", job_dir="/tmp/j1")
    assert job.job_id
    assert job.status == JobStatus.PENDING
    assert job.url == "https://example.com/reel/1"

def test_get_returns_none_when_missing():
    store = InMemoryJobStore()
    assert store.get("nope") is None

def test_get_current_returns_only_active_job():
    store = InMemoryJobStore()
    j1 = store.create(url="u1", job_dir="/tmp/j1")
    assert store.get_current() is not None
    store.set_status(j1.job_id, JobStatus.DONE)
    assert store.get_current() is None

def test_create_while_running_raises():
    store = InMemoryJobStore()
    store.create(url="u1", job_dir="/tmp/j1")
    with pytest.raises(RuntimeError, match="already running"):
        store.create(url="u2", job_dir="/tmp/j2")

def test_set_status_transitions():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_status(job.job_id, JobStatus.RUNNING)
    assert store.get(job.job_id).status == JobStatus.RUNNING

def test_set_stage_updates_current_stage():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_current_stage(job.job_id, "speech")
    assert store.get(job.job_id).current_stage == "speech"

def test_cancel_marks_canceled():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_status(job.job_id, JobStatus.CANCELED)
    assert store.get(job.job_id).status == JobStatus.CANCELED
    assert store.get_current() is None
