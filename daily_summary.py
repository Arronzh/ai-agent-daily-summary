import os
import feedparser
import requests
from datetime import datetime, timedelta
from openai import OpenAI

today = datetime.now().date()
yesterday = today - timedelta(days=1)

# 增加授权
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

# ==================== 1. 收集数据 ====================
items = []

# RSS 来源（国际 + 中文论坛 + 视频 + 更多微信公众号）
feeds = [
    "https://rsshub.app/github/trending/python/daily",
    "https://rsshub.app/github/trending/javascript/daily",
    "https://rsshub.app/reddit/r/AI_Agents/new",
    "https://rsshub.app/reddit/r/LocalLLaMA/new",
    "https://news.ycombinator.com/rss",
    "https://arxiv.org/rss/search_query=all:ai+agent+OR+multi-agent+OR+mcp+OR+\"agent+skills\"&searchtype=all&source=header",
    # 原有中文论坛
    "https://rsshub.app/zhihu/hotlist",
    "https://rsshub.app/csdn/index",
    "https://rsshub.app/juejin/trending/all/weekly",
    "https://rsshub.app/v2ex/topics/hot",
    # 视频平台
    "https://rsshub.app/bilibili/hot-search",
    "https://rsshub.app/bilibili/vsearch/AI%20智能体%20OR%20OpenClaw",
    "https://rsshub.app/youtube/search/AI%20Agent%20OR%20OpenClaw%20OR%20MCP",
    # ==================== 增强微信公众号（更多AI热门号） ====================
    "https://rsshub.app/wechat/mp/jiqizhixin",      # 机器之心
    "https://rsshub.app/wechat/mp/qbitai",           # 量子位
    "https://rsshub.app/wechat/mp/xinzhiyuan",       # 新智元
    "https://rsshub.app/wechat/mp/deeplearningtalk", # 深度学习大讲堂（若RSSHub支持，替换实际路径）
    "https://rsshub.app/wechat/mp/aitechcamp",       # AI科技大本营（示例，实际测试路径）
    # 可继续加：如 "https://rsshub.app/wechat/mp/xxxx" 
]

for url in feeds:
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:  # 每源限8条，公众号文章质量高
            try:
                pub_date = datetime(*entry.published_parsed[:6]).date()
                if pub_date >= yesterday:
                    desc = entry.get('summary', '')[:220]
                    source = url.split('/')[-1] if 'wechat' in url else url.split('/')[2].replace('rsshub.app', '').strip('/')
                    items.append({"title": entry.title, "link": entry.link, "desc": desc, "source": source})
            except:
                pass
    except:
        pass

# GitHub 新仓库搜索（含Agent关键词）
search_url = f"https://api.github.com/search/repositories?q=(\"ai agent\" OR \"agent skills\" OR mcp OR \"llm agent\" OR openclaw OR \"智能体\") created:>{yesterday.isoformat()}&sort=stars&order=desc&per_page=12"
gh_items = requests.get(search_url, headers={"Accept": "application/vnd.github.v3+json"}).json().get("items", [])
for repo in gh_items:
    items.append({
        "title": f"{repo['full_name']} - {repo.get('description', '')[:100]}",
        "link": repo['html_url'],
        "desc": f"⭐ {repo['stargazers_count']} stars",
        "source": "GitHub 新项目"
    })

# 核心框架监控（含OpenClaw）
framework_repos = [
    "langchain-ai/langgraph", "crewAIInc/crewAI", "microsoft/autogen",
    "run-llama/llama_index", "langgenius/dify", "FoundationAgents/MetaGPT",
    "deepset-ai/haystack", "microsoft/semantic-kernel", "openclaw/openclaw"
]

for repo in framework_repos:
    release_url = f"https://api.github.com/repos/{repo}/releases?per_page=2"
    releases = requests.get(release_url, headers={"Accept": "application/vnd.github.v3+json"}).json()
    if releases and isinstance(releases, list):
        for r in releases:
            try:
                pub_date = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")).date()
                if pub_date >= yesterday:
                    items.append({
                        "title": f"[{repo}] 新 Release: {r['tag_name']} - {r.get('name', '')}",
                        "link": r['html_url'],
                        "desc": r.get('body', '')[:150] + "...",
                        "source": "Framework Release"
                    })
                    break
            except:
                pass

# 去重 + 限制
items = list({item['link']: item for item in items}.values())[:45]

items_text = "\n".join([f"- **{item['title']}** ({item['source']}): {item['desc']}\n  → {item['link']}" for item in items])

# ==================== 2. Grok API 智能总结 ====================
client = OpenAI(
    api_key=os.getenv("GROK_API_KEY"),
    base_url="https://api.x.ai/v1"
)

prompt = f"""你是顶尖 AI 技术分析师。请严格用中文，对过去24小时 **AI Agent、Agent Skills、MCP、OpenClaw** 最新消息进行专业梳理总结。

特别重视微信公众号（如机器之心、量子位、新智元等）的最新文章、实战干货、国内Agent落地案例。

数据：
{items_text}

严格按照以下格式输出（专业、简洁、带 emoji）：

**📅 AI Agent & Skills 每日情报简报 ({today.strftime('%Y-%m-%d')})**

**🚀 头条热点**（4-6条最重要）

**📦 GitHub 亮点项目**（含 OpenClaw）

**📚 最新研究论文**

**🛠️ Agent Skills & 协议动态**（MCP、OpenClaw skills）

**🇨🇳 中文社区动态**（知乎/CSDN/掘金/微信公众号重点）

**📺 视频平台动态**（B站 & YouTube 新视频/教程）

**🌟 趋势洞察**（一句话总结）

**🔗 完整链接列表**
"""

response = client.chat.completions.create(
    model="grok-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)
summary = response.choices[0].message.content

# ==================== 3. 创建 GitHub Issue ====================
token = os.getenv("GITHUB_TOKEN")
repo = os.getenv("GITHUB_REPOSITORY")
issue_url = f"https://api.github.com/repos/{repo}/issues"

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
data = {
    "title": f"📅 AI Agent & Skills 每日情报简报 - {today}",
    "body": summary,
    "labels": ["daily-summary", "ai-agent", "openclaw", "微信公众号"]
}
requests.post(issue_url, json=data, headers=headers)
print("✅ 每日简报已生成并创建 Issue！")
