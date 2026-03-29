#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server酱推送模块"""

import os
import requests
from typing import Dict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ServerChanPusher:
    def __init__(self):
        self.sendkey = os.getenv('SERVERCHAN_SENDKEY', '')
        if not self.sendkey:
            raise ValueError("SERVERCHAN_SENDKEY 环境变量未设置")
        self.api_url = f"https://sctapi.ftqq.com/{self.sendkey}.send"
    
    def format_message(self, categorized: Dict) -> tuple:
        today = datetime.now().strftime('%Y-%m-%d')
        total = sum(len(items) for items in categorized.values())
        new_count = len(categorized.get("今日新内容", []))
        
        title = f"每日精选 ({new_count}条新内容)"
        
        lines = [f"## 📅 {today}\n", f"> 精选 {new_count} 条新内容，共 {total} 条\n", "---\n"]
        
        for cat in ["今日新内容", "重复提醒", "资源库"]:
            items = categorized.get(cat, [])
            if items:
                lines.append(f"### {cat}\n")
                for i, item in enumerate(items[:10], 1):
                    stars = f"⭐{item.stars:,} " if item.stars > 0 else ""
                    lines.append(f"**{i}. {item.name}** {stars}")
                    if item.description:
                        lines.append(f"> {item.description}")
                    lines.append(f"🔗 [查看]({item.link})\n")
                lines.append("---\n")
        
        lines.append("\n📱 *每日精选推送*")
        return title, "\n".join(lines)
    
    def push(self, categorized: Dict) -> bool:
        title, content = self.format_message(categorized)
        
        try:
            logger.info("正在推送...")
            response = requests.post(
                self.api_url,
                data={'title': title, 'desp': content},
                timeout=30
            )
            result = response.json()
            
            if result.get('code') == 0:
                logger.info("推送成功!")
                return True
            else:
                logger.error(f"推送失败: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"推送异常: {e}")
            return False
