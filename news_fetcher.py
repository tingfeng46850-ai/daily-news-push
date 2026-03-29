#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日精选推送模块"""

import os
import re
import json
import hashlib
import requests
import feedparser
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ToolItem:
    """内容条目"""
    name: str
    category: str
    source: str
    link: str
    description: str
    stars: int = 0
    quality_score: int = 0
    content_hash: str = ""
    is_new: bool = True
    is_duplicate: bool = False
    push_date: str = ""


STATIC_RESOURCES = {
    "国内AI工具": [
        {"name": "DeepSeek R1 - 深度思考免费模型", "url": "https://www.deepseek.com/", "desc": "国产最强推理模型，免费开放"},
        {"name": "Kimi - 20万字长文本AI", "url": "https://kimi.moonshot.cn/", "desc": "支持超长文本，完全免费"},
        {"name": "通义千问 - 阿里大模型", "url": "https://tongyi.aliyun.com/", "desc": "文档处理强，有免费API"},
        {"name": "智谱清言 - 清华GLM", "url": "https://chatglm.cn/", "desc": "开源模型，可私有部署"},
        {"name": "豆包 - 字节免费AI", "url": "https://www.doubao.com/", "desc": "完全免费，对话体验好"},
        {"name": "Cursor - AI编程神器", "url": "https://cursor.com/", "desc": "AI自动写代码"},
    ],
    "自动化工具": [
        {"name": "yt-dlp - 视频下载神器", "url": "https://github.com/yt-dlp/yt-dlp", "desc": "支持上千网站视频下载", "stars": 75000},
        {"name": "n8n - 工作流自动化", "url": "https://github.com/n8n-io/n8n", "desc": "可视化自动化工作流", "stars": 45000},
    ]
}


class HistoryManager:
    def __init__(self, history_file: str = "history.json"):
        self.history_file = history_file
        self.history: Dict[str, dict] = {}
        self._load()
    
    def _load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except:
                self.history = {}
    
    def save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史失败: {e}")
    
    def _hash(self, name: str, link: str) -> str:
        return hashlib.md5(f"{name}|{link}".encode()).hexdigest()[:16]
    
    def check_duplicate(self, item: ToolItem) -> Tuple[bool, int]:
        content_hash = self._hash(item.name, item.link)
        item.content_hash = content_hash
        
        if content_hash in self.history:
            record = self.history[content_hash]
            last_date = datetime.fromisoformat(record.get('date', '2000-01-01'))
            days_ago = (datetime.now() - last_date).days
            return True, days_ago
        return False, 0
    
    def mark_pushed(self, item: ToolItem):
        content_hash = item.content_hash or self._hash(item.name, item.link)
        self.history[content_hash] = {
            'title': item.name,
            'date': datetime.now().isoformat(),
            'category': item.category,
            'source': item.source
        }


class NewsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        self.timeout = 25
        self.history = HistoryManager()
    
    def fetch_all(self) -> dict:
        result = {
            "今日新内容": [],
            "重复提醒": [],
            "资源库": [],
        }
        
        logger.info("抓取动态内容...")
        dynamic_items = []
        dynamic_items.extend(self._fetch_ai_news())
        dynamic_items.extend(self._fetch_github_trending())
        dynamic_items.extend(self._fetch_tech_news())
        
        logger.info(f"抓取到 {len(dynamic_items)} 条动态内容")
        
        for item in dynamic_items:
            is_dup, days_ago = self.history.check_duplicate(item)
            
            if is_dup:
                if days_ago <= 1:
                    continue
                elif days_ago <= 7 and item.quality_score >= 8:
                    item.is_new = False
                    item.is_duplicate = True
                    item.push_date = f"{days_ago}天前推送过"
                    result["重复提醒"].append(item)
            else:
                item.is_new = True
                result["今日新内容"].append(item)
        
        result["今日新内容"] = sorted(result["今日新内容"], key=lambda x: x.quality_score, reverse=True)[:20]
        result["重复提醒"] = result["重复提醒"][:5]
        
        if len(result["今日新内容"]) < 15:
            result["资源库"] = self._get_static_resources()
        
        for item in result["今日新内容"]:
            self.history.mark_pushed(item)
        
        self.history.save()
        
        return result
    
    def _get_static_resources(self) -> List[ToolItem]:
        items = []
        
        for tool in STATIC_RESOURCES["国内AI工具"][:6]:
            item = ToolItem(
                name=tool["name"],
                category="资源库-国内AI工具",
                source="精选",
                link=tool["url"],
                description=tool["desc"],
                quality_score=7,
                is_new=False
            )
            items.append(item)
        
        for tool in STATIC_RESOURCES["自动化工具"][:4]:
            item = ToolItem(
                name=tool["name"],
                category="资源库-自动化工具",
                source="GitHub",
                link=tool["url"],
                description=tool["desc"],
                stars=tool.get("stars", 0),
                quality_score=7,
                is_new=False
            )
            items.append(item)
        
        return items
    
    def _fetch_ai_news(self) -> List[ToolItem]:
        items = []
        sources = [
            ("https://rsshub.app/hackernews/best", "Hacker News"),
            ("https://rsshub.app/36kr/newsflashes", "36氪"),
        ]
        
        seen_titles = set()
        
        for url, source in sources:
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:15]:
                    title = entry.get('title', '')
                    title_key = re.sub(r'\s+', '', title.lower())[:30]
                    if title_key in seen_titles:
                        continue
                    seen_titles.add(title_key)
                    
                    item = ToolItem(
                        name=self._clean_title(title),
                        category="AI动态",
                        source=source,
                        link=entry.get('link', ''),
                        description=self._clean_summary(entry.get('summary', '')),
                        quality_score=self._calc_score(title)
                    )
                    items.append(item)
                    
                    if len(items) >= 10:
                        break
            except Exception as e:
                logger.error(f"{source} 错误: {e}")
        
        return items
    
    def _fetch_github_trending(self) -> List[ToolItem]:
        items = []
        seen = set()
        
        try:
            url = "https://rsshub.app/github/trending/daily/any?limit=30"
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                for entry in feed.entries:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    summary = entry.get('summary', '') or ''
                    
                    match = re.search(r'([^/]+/[^/\s]+)', title)
                    name = match.group(1) if match else title
                    
                    if name in seen:
                        continue
                    seen.add(name)
                    
                    stars = 0
                    star_match = re.search(r'(\d+,?\d*)\s*star', summary, re.I)
                    if star_match:
                        stars = int(star_match.group(1).replace(',', ''))
                    
                    item = ToolItem(
                        name=name,
                        category="GitHub热门",
                        source="GitHub",
                        link=link,
                        description=self._clean_summary(summary, 60),
                        stars=stars,
                        quality_score=self._calc_score(name, stars)
                    )
                    items.append(item)
                    
                    if len(items) >= 10:
                        break
        except Exception as e:
            logger.error(f"GitHub热门错误: {e}")
        
        return items
    
    def _fetch_tech_news(self) -> List[ToolItem]:
        items = []
        seen_titles = set()
        
        sources = [
            ("https://rsshub.app/zhihu/hotlist", "知乎"),
            ("https://www.v2ex.com/api/topics/hot.json", "V2EX"),
        ]
        
        for url, source in sources:
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                
                if "v2ex" in url:
                    data = response.json()
                    for topic in data[:8]:
                        title = topic.get('title', '')
                        title_key = re.sub(r'\s+', '', title.lower())[:30]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)
                        
                        item = ToolItem(
                            name=self._clean_title(title),
                            category="科技资讯",
                            source="V2EX",
                            link=topic.get('url', ''),
                            description="",
                            quality_score=6
                        )
                        items.append(item)
                else:
                    feed = feedparser.parse(response.content)
                    for entry in feed.entries[:10]:
                        title = entry.get('title', '')
                        title_key = re.sub(r'\s+', '', title.lower())[:30]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)
                        
                        item = ToolItem(
                            name=self._clean_title(title),
                            category="科技资讯",
                            source=source,
                            link=entry.get('link', ''),
                            description=self._clean_summary(entry.get('summary', '')),
                            quality_score=6
                        )
                        items.append(item)
            except Exception as e:
                logger.error(f"{source} 科技资讯错误: {e}")
        
        return items
    
    def _calc_score(self, title: str, stars: int = 0) -> int:
        score = 5
        text = title.lower()
        
        if any(kw in text for kw in ['ai', 'gpt', 'llm', '免费', 'free', '开源', 'open']):
            score += 2
        if any(kw in text for kw in ['automation', '自动化', 'script', '脚本', 'tool', '工具']):
            score += 2
        if any(kw in text for kw in ['api', 'sdk', 'cli']):
            score += 1
        
        if stars > 10000:
            score += 2
        elif stars > 5000:
            score += 1
        
        return min(10, score)
    
    def _clean_title(self, title: str) -> str:
        title = re.sub(r'<[^>]+>', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title[:50] + "..." if len(title) > 50 else title
    
    def _clean_summary(self, summary: str, max_len: int = 60) -> str:
        summary = re.sub(r'<[^>]+>', '', summary)
        summary = re.sub(r'\s+', ' ', summary).strip()
        return summary[:max_len] + "..." if len(summary) > max_len else summary
