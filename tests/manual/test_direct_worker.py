#!/usr/bin/env python3
"""Direct test of crawl worker."""

import asyncio
import logging
from src.services.database import DatabaseManager
from src.logic.crawler.core.crawler import DocumentationCrawler
from src.lib.config import BablibConfig

logging.basicConfig(level=logging.DEBUG)

async def test_worker():
    config = BablibConfig()
    config.redis_url = "redis://localhost:6380"

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    crawler = DocumentationCrawler(db_manager, config)
    await crawler.initialize()

    try:
        # Get test box (box-centric architecture)
        box = await db_manager.get_box_by_name("test-box")
        if not box:
            print("Box not found")
            return

        # Create session manually with box_id
        session = await db_manager.create_crawl_session(
            box_id=box['id'],
            crawl_depth=box.get('crawl_depth', 3),
            user_agent="TestBot/1.0",
            rate_limit=1.0
        )
        session.start_session()
        await db_manager.update_crawl_session(session)

        # Set up crawler state
        crawler._current_session = session
        crawler._is_running = True
        crawler._stop_requested = False
        crawler._visited_urls.clear()
        crawler._content_hashes.clear()
        crawler._domain_last_access.clear()
        crawler._robots_cache.clear()

        # Create queue and add URL
        crawler._crawl_queue = asyncio.Queue()
        await crawler._crawl_queue.put((box.get('url', ''), 0, None))
        print(f"Queue size before worker: {crawler._crawl_queue.qsize()}")

        # Run worker directly with box
        from src.models.box import Box
        box_model = Box(id=box['id'], name=box['name'], type=box.get('type', 'drag'))
        await crawler._crawl_worker(box_model, session, max_pages=1)

        print(f"Worker completed")
        print(f"Pages crawled: {session.pages_crawled}")

    finally:
        await crawler.cleanup()
        await db_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(test_worker())