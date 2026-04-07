# 求职全流程自动化 AI Agent

一个能够自动化完成求职流程的智能 Agent，包括信息采集、智能筛选、简历定制和自动投递四大核心功能。

## 功能特性

### 1. 信息采集 (JobCollector)

- 多平台支持：BOSS 直聘、拉勾网、实习僧
- 智能爬取：自动抓取岗位信息，支持增量更新
- 反爬策略：请求延迟、IP 轮换、Cookie 管理
- 浏览器自动化：使用 Playwright 模拟真实浏览器行为
- 登录状态管理：保存和加载登录状态，减少登录次数
- 异常处理：请求失败时自动降级到网页解析模式
- 多平台分散请求：同时从多个平台采集，分散请求压力

### 2. 智能筛选 (JobFilter)

- 规则引擎：基于城市、薪资、学历等硬条件筛选
- 语义匹配：基于关键词和向量相似度计算匹配度
- 智能排序：按匹配度对岗位进行排序推荐

### 3. 简历定制 (ResumeAdapter)

- JD 解析：自动提取岗位要求的关键技能和 qualifications
- 智能适配：根据 JD 调整简历重点和技能顺序
- 多格式导出：支持文本、Markdown、HTML 格式

### 4. 自动投递 (AutoSubmitter)

- 浏览器自动化：使用 Playwright 实现表单自动填充
- 批量投递：支持并发投递，提高效率
- 质量保障：多重校验机制确保投递准确性

### 5. 质量保障 (QualityChecker)

- 简历质量检查：必填字段、格式、完整性验证
- 匹配度评估：技能覆盖、经验匹配、JD 契合度
- 投递验证：去重、每日限制、信息完整性

## 项目结构

```
求职全流程自动化 AI Agent/
├── config/                 # 配置文件
│   ├── config.py          # 配置管理类
│   └── .env.example       # 环境变量示例
├── data/                  # 数据目录
│   └── sample_resume.json # 示例简历
├── logs/                  # 日志目录（自动生成）
├── modules/               # 核心模块
│   ├── __init__.py
│   ├── models.py          # 数据模型
│   ├── job_collector.py   # 数据采集
│   ├── job_filter.py      # 智能筛选
│   ├── resume_adapter.py  # 简历定制
│   ├── auto_submitter.py  # 自动投递
│   └── quality_checker.py # 质量保障
├── utils/                 # 工具函数
│   ├── __init__.py
│   └── logger.py          # 日志工具
├── main.py                # 主程序入口
├── requirements.txt       # 依赖清单
└── README.md              # 说明文档
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install
```

### 2. 配置环境

```bash
# 复制环境变量模板
copy config\.env.example config\.env

# 编辑配置文件，填入你的 API Key
# 至少需要配置 LLM_API_KEY
```

### 3. 运行程序

```bash
# 默认运行（预览模式）
python main.py

# 自定义参数运行
python -c "from main import *; asyncio.run(main(keywords='java 实习', cities=['深圳']))"
```

## 配置说明

### 环境变量配置 (.env)

```env
# LLM API 配置
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# 或使用国内模型：
# LLM_API_KEY=your_qwen_api_key
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 爬虫配置
REQUEST_DELAY=1.0
MAX_RETRIES=3

# 筛选条件
DEFAULT_CITIES=北京，上海，深圳，杭州
MIN_SALARY=5000
MAX_SALARY=30000
JOB_TYPES=实习，全职

# 投递配置
AUTO_SUBMIT=false
DAILY_LIMIT=50

# 日志配置
LOG_LEVEL=INFO
```

## 使用示例

### 示例 1: 基础搜索

```python
from main import JobSearchAgent, create_sample_resume
import asyncio

async def search():
    agent = JobSearchAgent()
    resume = create_sample_resume()

    await agent.run(
        keywords="python 实习",
        cities=["北京", "上海"],
        max_salary=25,
        is_intern=True,
        resume=resume,
        pages_per_platform=3,
        auto_submit=False
    )

asyncio.run(search())
```

### 示例 2: 自定义简历

```python
from modules.models import Resume

resume = Resume(
    name="你的名字",
    phone="你的手机号",
    email="你的邮箱",
    education=[
        {
            'school': '你的学校',
            'major': '你的专业',
            'degree': '本科/硕士'
        }
    ],
    skills=['Python', 'Java', 'MySQL', ...],
    # ... 其他字段
)
```

### 示例 3: 批量处理

```python
# 采集岗位
jobs = await agent.collector.search_jobs(
    keywords="前端实习",
    cities=["杭州"],
    pages_per_platform=5
)

# 筛选
filtered = agent.filter.filter_and_rank(jobs, resume_skills=resume.skills)

# 展示推荐
agent._show_recommendations(filtered[:20])
```

## 模块详解

### JobCollector - 数据采集

支持的平台:

- BossZhipinPlatform: BOSS 直聘
- LAGouPlatform: 拉勾网
- InternSengPlatform: 实习僧

反爬机制:

- **浏览器自动化**：使用 Playwright 启动真实浏览器，模拟用户行为
- **隐形模式**：注入 stealth 脚本，隐藏浏览器的自动化特征
- **请求频率控制**：添加 1-3 秒的随机延时，避免短时间内发送大量请求
- **登录状态管理**：保存登录凭证到本地文件，避免重复登录
- **异常处理**：API 请求失败时自动降级到网页解析模式
- **多平台分散**：同时从多个平台采集，分散请求压力

```python
collector = JobCollector(
    platforms=['boss_zhipin', 'lagou'],
    request_delay=1.0
)

jobs = await collector.search_jobs(
    keywords="数据分析",
    cities=["北京"],
    max_salary=30,
    is_intern=True,
    pages_per_platform=3
)
```

### JobFilter - 智能筛选

筛选策略:

1. 规则筛选：硬条件过滤（城市、薪资等）
2. 语义匹配：技能关键词匹配
3. 智能排序：综合评分排序

```python
filter = JobFilter({
    'cities': ['北京', '上海'],
    'min_salary': 5000,
    'max_salary': 30000,
    'min_score': 60
})

filtered_jobs = filter.filter_and_rank(
    jobs,
    resume_skills=resume.skills,
    resume_keywords=keywords
)
```

### ResumeAdapter - 简历定制

定制功能:

- 根据 JD 调整自我评价
- 重新排序技能列表
- 提取关键技能关键词

```python
adapter = ResumeAdapter()
adapted_resume = adapter.adapt(resume, job)

# 导出为不同格式
text = ResumeGenerator.to_text(adapted_resume)
html = ResumeGenerator.to_html(adapted_resume)
```

### AutoSubmitter - 自动投递

投递流程:

1. 启动浏览器
2. 打开岗位页面
3. 填写表单
4. 上传简历
5. 提交申请

```python
submitter = AutoSubmitterManager(
    auto_submit=True,
    daily_limit=50
)

await submitter.initialize()
result = await submitter.submit_job(job, resume)
await submitter.shutdown()
```

### QualityChecker - 质量保障

检查项:

- 必填字段完整性
- 联系方式格式
- 教育/工作经历
- 技能覆盖度
- JD 匹配度

```python
checker = QualityAssuranceManager()
result = checker.comprehensive_check(
    resume=resume,
    job=job,
    match_score=85,
    daily_count=10
)

if result.passed:
    print("质量检查通过")
else:
    print("建议:", result.suggestions)
```

## 注意事项

### 法律合规

1. 遵守各招聘平台的 robots.txt 协议
2. 控制请求频率，避免对服务器造成压力
3. 仅用于个人求职，不得用于商业目的

### 技术限制

1. 网站结构变化可能导致爬虫失效
2. 部分平台有严格的反爬措施
3. 自动投递需要手动登录验证

### 数据安全

1. 不要泄露个人隐私信息
2. API Key 妥善保管，不要提交到代码库
3. 建议使用本地部署，避免云端传输敏感数据

## 扩展开发

### 添加新平台

```python
from modules.job_collector import JobPlatformInterface, JobPosition

class NewPlatform(JobPlatformInterface):
    @property
    def platform_name(self):
        return "new_platform"

    async def search_jobs(self, keywords, city, **kwargs):
        # 实现搜索逻辑
        pass

    async def get_job_detail(self, job_id, url):
        # 实现详情获取逻辑
        pass
```

### 自定义筛选规则

```python
from modules.job_filter import RuleEngine

class CustomRuleEngine(RuleEngine):
    def _check_city(self, job):
        # 自定义城市筛选逻辑
        pass

    def _check_company(self, job):
        # 新增公司类型筛选
        pass
```

### 集成 LLM 优化

```python
from langchain.chat_models import ChatOpenAI
from modules.resume_adapter import ResumeAdapter

llm = ChatOpenAI(model="gpt-4", temperature=0.7)
adapter = ResumeAdapter(llm_client=llm)
```

## 性能指标

- 采集速度：~100 岗位/分钟（单平台）
- 筛选速度：~1000 岗位/秒
- 简历生成：< 1 秒
- 投递成功率：~80%（取决于平台反爬）

## 贡献指南

欢迎提交 Issue 和 Pull Request!

## 许可证

MIT License

## 致谢

- Playwright - 浏览器自动化工具
- LangChain - LLM 应用框架
- 各招聘平台提供的公开数据

---

注意：本项目仅供学习和研究使用，请遵守相关法律法规和各平台的使用条款。
