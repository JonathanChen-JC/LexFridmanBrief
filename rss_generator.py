import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator
from collections import deque
import xml.etree.ElementTree as ET

def create_rss_feed():
    fg = FeedGenerator()
    fg.title('Lex Fridman Podcast Brief')
    fg.link(href='https://lexfridman.com/')
    fg.description('Brief summaries of Lex Fridman Podcast episodes')
    fg.language('zh-CN')
    return fg

def parse_existing_feed(feed_path):
    if not os.path.exists(feed_path):
        return deque(maxlen=50)
    
    try:
        tree = ET.parse(feed_path)
        root = tree.getroot()
        entries = deque(maxlen=50)
        
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            description = item.find('description').text
            pub_date = item.find('pubDate').text
            entries.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date
            })
        return entries
    except Exception as e:
        print(f"Error parsing existing feed: {e}")
        return deque(maxlen=50)

def format_content(content):
    # 按照多个换行符分割段落，使用HTML标签格式化
    lines = content.split('\n')
    formatted_lines = []
    current_paragraph = []
    
    for line in lines:
        line = line.rstrip()
        
        # 处理标题行（以#开头）
        if line.lstrip().startswith('#'):
            # 如果有待处理的段落，先添加它
            if current_paragraph:
                formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
                current_paragraph = []
            
            formatted_lines.append(line)
            formatted_lines.append('')  # 标题后添加一个空行
        # 处理空行：表示段落结束
        elif not line.strip():
            if current_paragraph:
                formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
                current_paragraph = []
        # 处理普通文本行
        else:
            current_paragraph.append(line)
    
    # 处理最后一个段落
    if current_paragraph:
        formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
    
    # 使用单个换行符连接所有行
    return '\n'.join(formatted_lines)

def update_feed():
    brief_dir = os.path.join(os.path.dirname(__file__), 'brief')
    feed_path = os.path.join(os.path.dirname(__file__), 'feed.xml')
    
    # 如果feed.xml不存在，创建新的feed
    if not os.path.exists(feed_path):
        fg = create_rss_feed()
        existing_entries = deque(maxlen=50)
    else:
        # 如果feed.xml存在，解析现有的feed
        fg = FeedGenerator()
        tree = ET.parse(feed_path)
        root = tree.getroot()
        
        # 复制现有feed的基本信息
        channel = root.find('channel')
        fg.title(channel.find('title').text)
        fg.link(href=channel.find('link').text)
        fg.description(channel.find('description').text)
        fg.language(channel.find('language').text)
        
        # 获取现有条目
        existing_entries = parse_existing_feed(feed_path)
    
    # 获取最新的brief文件
    latest_brief = None
    latest_mtime = 0
    for filename in os.listdir(brief_dir):
        if filename.endswith('.md'):
            file_path = os.path.join(brief_dir, filename)
            mtime = os.path.getmtime(file_path)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_brief = filename
    
    # 如果找到最新的brief文件，检查是否需要添加到feed
    if latest_brief:
        title = latest_brief[:-3]  # 移除.md后缀
        
        # 检查是否已存在相同标题的条目
        if not any(entry['title'] == title for entry in existing_entries):
            file_path = os.path.join(brief_dir, latest_brief)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 格式化内容，保持原有段落格式
            formatted_content = format_content(content)
            
            # 创建新条目
            current_time = datetime.now(ZoneInfo('Asia/Shanghai'))
            new_entry = {
                'title': title,
                'link': 'https://lexfridman.com/',
                'description': formatted_content,
                'pub_date': current_time.strftime('%a, %d %b %Y %H:%M:%S %z')
            }
            
            # 添加新条目到feed
            fe = fg.add_entry()
            fe.title(new_entry['title'])
            fe.link(href=new_entry['link'])
            fe.description(new_entry['description'])
            fe.pubDate(datetime.strptime(new_entry['pub_date'], '%a, %d %b %Y %H:%M:%S %z'))
            
            # 添加新条目到现有条目列表
            existing_entries.append(new_entry)
            
            # 将现有条目添加到feed中（除了刚刚添加的新条目）
            for entry in list(existing_entries)[:-1]:
                fe = fg.add_entry()
                fe.title(entry['title'])
                fe.link(href=entry['link'])
                fe.description(entry['description'])
                fe.pubDate(datetime.strptime(entry['pub_date'], '%a, %d %b %Y %H:%M:%S %z'))
            
            # 生成feed并写入文件
            fg.rss_file(feed_path, pretty=True)