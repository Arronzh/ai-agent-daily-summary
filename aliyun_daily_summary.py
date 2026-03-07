import os
import feedparser
import requests
from datetime import datetime, timedelta
from openai import OpenAI  # 仍然使用 openai 库，但配置为阿里云端点

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
    "https://rsshub.app/wechat/mp/deeplearningtalk", # 深度学习大讲堂
    "https://rsshub.app/wechat/mp/aitechcamp",       # AI科技大本营
]

for url in feeds:
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
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
gh_items = requests.get(search_url, headers=HEADERS).json().get("items",[])
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
    releases = requests.get(release_url, headers=HEADERS).json()
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

# ==================== 2. 阿里云 Coding Plan API 智能总结 ====================
# 关键修改：使用 Coding Plan 专属 API 配置
client = OpenAI(
    api_key=os.getenv("API_KEY"),  # 从环境变量获取
    base_url="https://coding.dashscope.aliyuncs.com/v1",  # Coding Plan 专属端点
)

# 优化提示词，更适配通义千问模型
prompt = f"""你是一个专业的AI技术分析助手，需要总结过去24小时关于AI Agent、Agent Skills、MCP、OpenClaw等领域的最新动态。

请基于以下数据，生成一份专业的每日情报简报：

{items_text}

**请严格按照以下格式输出（使用中文）：**

**📅 AI Agent & Skills 每日情报简报 ({today.strftime('%Y-%m-%d')})**

**🚀 今日头条**（4-6条最重要的动态）

**📦 GitHub 亮点项目**（包含OpenClaw相关的新项目或更新）

**📚 研究进展**（最新的AI论文或研究成果）

**🛠️ 技术动态**（MCP、Agent Skills、OpenClaw技能等协议和工具更新）

**🇨🇳 中文社区**（知乎、CSDN、掘金、微信公众号等重点内容）

**📺 视频动态**（B站和YouTube上的相关新视频或教程）

**🌟 趋势观察**（一句话总结今日核心趋势）

**🔗 参考链接**（所有提到的链接列表）

**要求：**
1. 内容简洁专业，避免冗余
2. 重点突出OpenClaw、Agent Skills和MCP相关内容
3. 微信公众号内容需特别关注
4. 使用适当的emoji增强可读性
"""

try:
    response = client.chat.completions.create(
        model="qwen3.5-plus",  # 推荐使用通义千问3.5增强版
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # 降低随机性，确保内容准确
        max_tokens=2000
    )
    summary = response.choices[0].message.content
except Exception as e:
    print(f"❌ API调用失败: {e}")
    # 备选方案：如果API调用失败，生成简化版摘要
    summary = f"""**📅 AI Agent & Skills 每日情报简报 ({today.strftime('%Y-%m-%d')})**

今日共收集到 {len(items)} 条相关信息。

由于API调用失败，以下是简化版摘要：

**收集到的来源包括：**
- GitHub趋势项目
- 知乎、CSDN、掘金等中文社区
- 机器之心、量子位、新智元等微信公众号
- B站、YouTube视频平台
- arXiv研究论文

**完整链接列表：**
{chr(10).join([f"- [{item['title'][:50]}...]({item['link']})" for item in items[:10]])}
...
"""
    # 记录错误到日志
    with open("error.log", "a") as f:
        f.write(f"{datetime.now()}: {e}\n")

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

try:
    response = requests.post(issue_url, json=data, headers=headers)
    if response.status_code == 201:
        print("✅ 每日简报已成功生成并创建 GitHub Issue！")
        print(f"🔗 Issue 链接: {response.json()['html_url']}")
    else:
        print(f"❌ 创建 Issue 失败: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ 请求失败: {e}")

# 同时保存到本地文件
filename = f"daily_summary_{today}.md"
with open(filename, "w", encoding="utf-8") as f:
    f.write(summary)
print(f"📁 简报已保存到本地文件: {filename}")
