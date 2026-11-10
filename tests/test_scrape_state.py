"""Queue resume/fresh-start logic and the per-run logfile.

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import saflii_processor_yearly as p  # noqa: E402
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


if __name__ == "__main__":
    test_request_queue_resume_or_fresh()
    test_logfile_survives_crawler_init()
    print("OK")
