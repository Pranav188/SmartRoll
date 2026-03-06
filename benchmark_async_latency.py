#!/usr/bin/env python3
import os
import statistics
import time
import uuid
from pathlib import Path
from unittest.mock import patch


def percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_values) - 1)))
    return float(sorted_values[idx])


def summarize(times_ms):
    s = sorted(times_ms)
    return {
        "n": len(times_ms),
        "mean_ms": statistics.mean(times_ms),
        "p50_ms": percentile(s, 50),
        "p95_ms": percentile(s, 95),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
    }


def print_summary(label, stats):
    print(f"{label}: n={stats['n']} mean={stats['mean_ms']:.2f}ms p50={stats['p50_ms']:.2f}ms p95={stats['p95_ms']:.2f}ms min={stats['min_ms']:.2f}ms max={stats['max_ms']:.2f}ms")


def run_mode(client, sample_image_path, mode, runs):
    from core import views
    from core.models import Student
    from core.face_recognition_engine import rebuild_encodings_task

    def cleanup(prefix):
        Student.objects.filter(name__startswith=prefix).delete()
        dataset_dir = Path("dataset")
        if dataset_dir.exists():
            for p in dataset_dir.glob(f"{prefix}*"):
                if p.is_dir():
                    for fp in p.glob("**/*"):
                        if fp.is_file():
                            fp.unlink(missing_ok=True)
                    for dp in sorted(p.glob("**/*"), reverse=True):
                        if dp.is_dir():
                            dp.rmdir()
                    p.rmdir()

    def cleanup_one(student_name):
        Student.objects.filter(name=student_name).delete()
        p = Path("dataset") / student_name
        if p.exists() and p.is_dir():
            for fp in p.glob("**/*"):
                if fp.is_file():
                    fp.unlink(missing_ok=True)
            for dp in sorted(p.glob("**/*"), reverse=True):
                if dp.is_dir():
                    dp.rmdir()
            p.rmdir()

    prefix = f"bench_{mode}_"
    cleanup(prefix)

    if mode == "async":
        patcher = patch.object(views.rebuild_encodings_task, "delay", lambda *args, **kwargs: None)
    elif mode == "sync":
        patcher = patch.object(views.rebuild_encodings_task, "delay", lambda *args, **kwargs: rebuild_encodings_task())
    else:
        raise ValueError("mode must be async or sync")

    times_ms = []
    with patcher:
        for i in range(runs):
            student_name = f"{prefix}{uuid.uuid4().hex[:8]}_{i}"
            with open(sample_image_path, "rb") as f:
                t0 = time.perf_counter()
                resp = client.post(
                    "/students/add/",
                    data={"student_name": student_name, "photos": f},
                )
                dt = (time.perf_counter() - t0) * 1000.0
            if resp.status_code not in (302, 200):
                raise RuntimeError(f"Unexpected status {resp.status_code} in {mode} run {i}")
            times_ms.append(dt)
            print(f"{mode} run {i+1}/{runs}: {dt:.2f}ms")
            cleanup_one(student_name)

    cleanup(prefix)
    return times_ms


def main():
    # Isolate benchmark from external services for reproducibility in local dev shell.
    os.environ.setdefault("SECRET_KEY", "bench-secret")
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
    os.environ.setdefault("DATABASE_URL", "sqlite:///bench.sqlite3")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_roll.settings")

    import django
    django.setup()

    from django.core.management import call_command
    from django.conf import settings
    from django.test import Client

    settings.ALLOWED_HOSTS = list(set(settings.ALLOWED_HOSTS + ["testserver", "127.0.0.1", "localhost"]))

    call_command("migrate", verbosity=0)

    sample_image_path = None
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        found = list(Path("dataset").glob(f"*/*{ext[1:]}"))
        if found:
            sample_image_path = found[0]
            break
    if sample_image_path is None:
        raise FileNotFoundError("No sample image found under dataset/<student>/*")

    print(f"Using sample image: {sample_image_path}")
    client = Client()

    async_times = run_mode(client, sample_image_path, mode="async", runs=5)
    sync_times = run_mode(client, sample_image_path, mode="sync", runs=3)

    async_stats = summarize(async_times)
    sync_stats = summarize(sync_times)

    print("\nSummary")
    print_summary("async", async_stats)
    print_summary("sync", sync_stats)

    reduction_mean = ((sync_stats["mean_ms"] - async_stats["mean_ms"]) / sync_stats["mean_ms"]) * 100.0
    reduction_p50 = ((sync_stats["p50_ms"] - async_stats["p50_ms"]) / sync_stats["p50_ms"]) * 100.0
    print(f"Reduction (mean): {reduction_mean:.2f}%")
    print(f"Reduction (p50): {reduction_p50:.2f}%")


if __name__ == "__main__":
    main()
