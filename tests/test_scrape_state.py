"""Court filter list, queue resume/fresh-start, per-run logfile, dashboard status.

Run: uv run python tests/test_scrape_state.py  (or pytest, if installed)
"""

import asyncio
import glob
import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
# Like the container: keep the queue across process starts
os.environ["CRAWLEE_STORAGE_DIR"] = os.path.join(TMP, "storage")
os.environ["CRAWLEE_PURGE_ON_START"] = "false"
os.environ["SAFLII_DATA_DIR"] = TMP
os.environ["SAFLII_STATUS_PORT"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402
import threading  # noqa: E402
import urllib.request  # noqa: E402

import saflii_processor_yearly as p  # noqa: E402
import scheduler  # noqa: E402
from crawlee import Request  # noqa: E402
from crawlee.crawlers import BeautifulSoupCrawler  # noqa: E402


async def _check_queue():
    queue = await p.open_request_queue()
    await queue.add_request(Request.from_url("https://example.org/a"))
    await queue.mark_request_as_handled(await queue.fetch_next_request())

    # Finished queue -> next run starts fresh (the Oct 2026 "0 requests" bug)
    queue = await p.open_request_queue()
    assert await queue.get_handled_count() == 0

    # Unfinished queue -> next run resumes
    await queue.add_request(Request.from_url("https://example.org/b"))
    queue = await p.open_request_queue()
    assert await queue.get_total_count() == 1


def test_request_queue_resume_or_fresh():
    asyncio.run(_check_queue())


def test_logfile_survives_crawler_init():
    BeautifulSoupCrawler()  # strips all root-logger handlers
    p.setup_file_logging(TMP)
    p.log.info("after-crawler-init")
    assert any(
        "after-crawler-init" in open(f).read() for f in glob.glob(f"{TMP}/logs/*.log")
    )


def test_court_filter_list():
    config = p.ScraperConfig(" ZASCA, ZAGPJHC ", None, "html")
    assert config.courts == ["ZASCA", "ZAGPJHC"]
    assert p.build_start_urls(config) == [
        "https://www.saflii.org/za/cases/ZASCA/",
        "https://www.saflii.org/za/cases/ZAGPJHC/",
    ]
    assert p.ScraperConfig(None, None, "html").courts == []


def _touch(*parts):
    path = os.path.join(TMP, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()


def test_status_counts_and_endpoint():
    _touch("pdf/za/cases/ZACC/2025/a.pdf")
    _touch("pdf/za/cases/ZACC/2026/b.pdf")
    _touch("pdf/za/cases/ZACC/2026/@eaDir/b.pdf/SYNOINDEX")  # Synology noise
    _touch("html/za/cases/ZACC/2026/b.html")
    _touch("html/za/cases/ZASCA/2024/c.html")
    courts = p.count_collection(TMP)
    assert courts == [
        {"court": "ZACC", "pdf": 2, "html": 1, "latest_year": "2026"},
        {"court": "ZASCA", "pdf": 0, "html": 1, "latest_year": "2024"},
    ]
    assert p.collection_totals(courts) == {"pdf": 2, "html": 2}

    p.write_status(TMP, {"running": True, "courts": courts})
    assert p.read_status(TMP)["running"] is True

    scheduler.save_state({"saflii-scrape": scheduler.datetime(2026, 11, 1, 0, 0)})
    server = scheduler.ThreadingHTTPServer(("127.0.0.1", 0), scheduler.StatusHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/status.json") as r:
        served = json.load(r)
    server.shutdown()
    assert served["courts"][0]["court"] == "ZACC"
    assert served["next_run_due"] == "2026-11-08 00:00"


if __name__ == "__main__":
    test_status_counts_and_endpoint()
    test_court_filter_list()
    test_request_queue_resume_or_fresh()
    test_logfile_survives_crawler_init()
    print("OK")
