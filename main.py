#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日精选推送主程序"""

import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_fetcher import NewsFetcher
from push_notification import ServerChanPusher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info(f"每日精选推送 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    if not os.getenv('SERVERCHAN_SENDKEY'):
        logger.error("SERVERCHAN_SENDKEY 未设置")
        sys.exit(1)
    
    try:
        logger.info("开始抓取...")
        fetcher = NewsFetcher()
        categorized = fetcher.fetch_all()
        
        total = sum(len(items) for items in categorized.values())
        new_count = len(categorized.get("今日新内容", []))
        
        logger.info(f"抓取到 {total} 条内容, 新内容 {new_count} 条")
        
        if total == 0:
            logger.warning("无内容可推送")
            sys.exit(0)
        
        logger.info("开始推送...")
        pusher = ServerChanPusher()
        success = pusher.push(categorized)
        
        if success:
            logger.info("任务完成!")
        else:
            logger.error("推送失败")
            sys.exit(1)
    
    except Exception as e:
        logger.exception(f"执行出错: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()