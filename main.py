"""
求职全流程自动化 AI Agent - 主程序

功能模块:
1. 信息采集 - 从多个招聘平台自动抓取岗位信息
2. 智能筛选 - 根据设定条件筛选匹配的岗位
3. 简历定制 - 根据目标岗位的 JD 自动调整和优化简历
4. 自动投递 - 将定制后的简历投递至目标岗位

使用方法:
    python main.py

配置说明:
    1. 复制并修改 config/.env.example 为 config/.env
    2. 填入你的 API Key 和配置参数
    3. 运行主程序即可
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from modules.models import Resume, JobPosition
from modules.job_collector import JobCollector
from modules.job_filter import JobFilter
from modules.resume_adapter import ResumeOptimizer
from modules.auto_submitter import AutoSubmitterManager
from modules.quality_checker import QualityAssuranceManager
from utils.logger import log
from config.config import settings


class JobSearchAgent:
    """求职搜索 Agent - 整合所有功能模块"""
    
    def __init__(self):
        """初始化 Agent"""
        log.info("求职全流程自动化 AI Agent 启动中...")
        
        # 初始化各模块（使用 Playwright 浏览器模式）
        self.collector = JobCollector(
            platforms=['boss_zhipin', 'lagou', 'internseng'],
            request_delay=settings.REQUEST_DELAY,
            use_browser=True  # 启用浏览器模式
        )
        
        self.filter = JobFilter({
            'cities': settings.DEFAULT_CITIES,
            'min_salary': settings.MIN_SALARY,
            'max_salary': settings.MAX_SALARY,
            'job_types': settings.JOB_TYPES,
            'min_score': 60
        })
        
        # 初始化简历适配器（使用 Qwen LLM）
        self.resume_optimizer = ResumeOptimizer(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL
        )
        
        # 兼容旧的 resume_adapter 名称
        self.resume_adapter = self.resume_optimizer
        
        self.submitter = AutoSubmitterManager(
            auto_submit=settings.AUTO_SUBMIT,
            daily_limit=settings.DAILY_LIMIT
        )
        
        self.quality_checker = QualityAssuranceManager()
        
        log.success("所有模块初始化完成")
    
    async def run(self, 
                  keywords: str = "python 实习",
                  cities: List[str] = None,
                  max_salary: int = 30,
                  is_intern: bool = True,
                  resume: Resume = None,
                  pages_per_platform: int = 3,
                  auto_submit: bool = None):
        """
        执行完整的求职流程
        
        Args:
            keywords: 搜索关键词
            cities: 目标城市列表
            max_salary: 最高薪资（K）
            is_intern: 是否只搜索实习
            resume: 简历对象
            pages_per_platform: 每个平台搜索页数
            auto_submit: 是否自动投递（None 使用配置值）
        """
        try:
            # 设置默认值
            cities = cities or settings.DEFAULT_CITIES
            auto_submit = auto_submit if auto_submit is not None else settings.AUTO_SUBMIT
            
            log.info(f"\n{'='*60}")
            log.info(f"开始求职搜索任务")
            log.info(f"关键词：{keywords}")
            log.info(f"城市：{cities}")
            log.info(f"最大薪资：{max_salary}K")
            log.info(f"{'='*60}\n")
            
            # Step 1: 数据采集
            jobs = await self._collect_jobs(
                keywords=keywords,
                cities=cities,
                max_salary=max_salary,
                is_intern=is_intern,
                pages_per_platform=pages_per_platform
            )
            
            if not jobs:
                log.error("未获取到任何岗位，请检查配置或网络")
                return
            
            log.info(f"\n共获取 {len(jobs)} 个岗位\n")
            
            # Step 2: 智能筛选
            filtered_jobs = self._filter_jobs(jobs, resume)
            
            if not filtered_jobs:
                log.warning("筛选后无匹配岗位，尝试放宽条件...")
                filtered_jobs = self._filter_jobs(jobs, resume, relaxed=True)
            
            log.info(f"筛选后剩余 {len(filtered_jobs)} 个高匹配岗位\n")
            
            # Step 3: 简历定制与投递
            if resume:
                await self._submit_jobs(filtered_jobs, resume, auto_submit)
            else:
                log.info("未提供简历，仅展示推荐岗位")
                self._show_recommendations(filtered_jobs[:10])
            
            log.success("\n求职任务完成！")
            
        except KeyboardInterrupt:
            log.warning("\n用户中断操作")
        except Exception as e:
            log.error(f"\n程序异常：{str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()
    
    async def _collect_jobs(self, **kwargs) -> List[JobPosition]:
        """采集岗位信息 - 使用 Playwright 真实爬虫"""
        log.info("Step 1: 正在采集岗位信息...")
        
        # 启动浏览器
        await self.collector.start()
        
        try:
            jobs = await self.collector.search_jobs(**kwargs)
            
            if not jobs:
                log.warning("未采集到岗位，可能是反爬限制或网络问题")
                log.info("提示：可以尝试以下方案")
                log.info("1. 使用官方 API（需要申请）")
                log.info("2. 提供登录 Cookie")
                log.info("3. 使用代理 IP")
            
            log.success(f"成功采集 {len(jobs)} 个岗位")
            return jobs
            
        finally:
            # 关闭浏览器
            await self.collector.close()
    
    def _filter_jobs(self, jobs: List[JobPosition], 
                     resume: Resume = None,
                     relaxed: bool = False) -> List[JobPosition]:
        """筛选岗位"""
        log.info("Step 2: 正在智能筛选岗位...")
        
        # 准备简历信息
        resume_skills = resume.skills if resume else []
        resume_keywords = self._extract_resume_keywords(resume) if resume else []
        
        # 调整筛选策略
        if relaxed:
            self.filter.min_score = 40
        else:
            self.filter.min_score = 60
        
        # 执行筛选
        filtered_jobs = self.filter.filter_and_rank(
            jobs,
            resume_skills=resume_skills,
            resume_keywords=resume_keywords
        )
        
        log.success(f"筛选完成，推荐 {len(filtered_jobs)} 个岗位")
        return filtered_jobs
    
    def _extract_resume_keywords(self, resume: Resume) -> List[str]:
        """提取简历关键词"""
        keywords = []
        
        # 从技能中提取
        keywords.extend(resume.skills)
        
        # 从教育背景中提取
        for edu in resume.education:
            keywords.append(edu.get('major', ''))
        
        # 从工作经历中提取
        for exp in resume.work_experience:
            keywords.append(exp.get('position', ''))
        
        return list(set([k for k in keywords if k]))
    
    async def _submit_jobs(self, jobs: List[JobPosition], 
                          resume: Resume,
                          auto_submit: bool):
        """投递岗位"""
        log.info("Step 3: 正在处理投递...")
        
        # 初始化投递器
        await self.submitter.initialize()
        
        # 质量检查
        top_jobs = jobs[:5]  # 先处理前 5 个
        for job in top_jobs:
            # 质量检查
            result = self.quality_checker.comprehensive_check(
                resume=resume,
                job=job,
                match_score=job.score,
                daily_count=self.submitter.daily_count
            )
            
            if not result.passed:
                log.warning(f"{job.title} 质量检查未通过")
                log.warning(f"   建议：{result.suggestions}")
                continue
            
            # 简历定制
            adapted_resume = self.resume_adapter.adapt(resume, job)
            
            # 执行投递
            success = await self.submitter.submit_job(job, adapted_resume)
            
            if not success:
                log.error(f"{job.title} 投递失败")
        
        # 批量投递（如果启用自动投递）
        if auto_submit and len(jobs) > 5:
            log.info("\n开始批量投递剩余岗位...")
            results = await self.submitter.batch_submit(
                jobs[5:],
                resume,
                max_concurrent=3
            )
            log.info(f"批量投递结果：成功={results['success']}, 失败={results['failed']}")
        
        await self.submitter.shutdown()
    
    def _show_recommendations(self, jobs: List[JobPosition]):
        """展示推荐岗位"""
        log.info("\n" + "="*60)
        log.info("推荐岗位列表")
        log.info("="*60)
        
        for i, job in enumerate(jobs, 1):
            log.info(f"\n{i}. {job.title} @ {job.company}")
            log.info(f"   城市：{job.city}")
            log.info(f"   薪资：{job.get_salary_range()}")
            log.info(f"   类型：{job.job_type}")
            log.info(f"   匹配度：{job.score:.1f}%")
            log.info(f"   链接：{job.url}")
        
        log.info("\n" + "="*60)
    
    async def _cleanup(self):
        """清理资源"""
        log.info("\n正在清理资源...")
        # 这里可以添加清理逻辑
        log.success("资源清理完成")


def create_sample_resume() -> Resume:
    """创建示例简历"""
    return Resume(
        name="张三",
        phone="13800138000",
        email="zhangsan@example.com",
        education=[
            {
                'school': '某某大学',
                'major': '计算机科学与技术',
                'degree': '本科',
                'time': '2020-2024'
            }
        ],
        work_experience=[
            {
                'company': '某某科技公司',
                'position': '后端开发实习生',
                'time': '2023-06 至 2023-09',
                'description': '参与公司核心业务系统开发，使用 Python/Django 实现多个功能模块'
            }
        ],
        projects=[
            {
                'name': '在线商城系统',
                'description': '基于 Spring Boot + MySQL 的电商系统，支持商品管理、订单处理等功能'
            },
            {
                'name': '数据分析平台',
                'description': '使用 Python + Pandas + Matplotlib 进行数据分析和可视化展示'
            }
        ],
        skills=[
            'Python', 'Java', 'MySQL', 'MongoDB',
            'Django', 'Spring Boot', 'Git', 'Linux',
            'Docker', 'RESTful API', 'HTML/CSS', 'JavaScript'
        ],
        certificates=[
            '英语六级 (CET-6)',
            '计算机等级考试 (三级 - 数据库技术)'
        ],
        self_evaluation=(
            "热爱编程，具备扎实的数据结构和算法基础。"
            "有实际项目开发经验，能够快速学习新技术。"
            "具备良好的团队协作能力和沟通能力。"
        )
    )


async def main():
    """主函数"""
    log.info("求职全流程自动化 AI Agent v1.0")
    log.info("功能：信息采集 | 智能筛选 | 简历定制 | 自动投递")
    
    # 创建 Agent 实例
    agent = JobSearchAgent()
    
    # 创建示例简历
    resume = create_sample_resume()
    
    # 执行求职流程
    await agent.run(
        keywords="python 实习",
        cities=["北京", "上海"],
        max_salary=25,
        is_intern=True,
        resume=resume,
        pages_per_platform=2,
        auto_submit=False  # 默认不自动投递，先预览
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
