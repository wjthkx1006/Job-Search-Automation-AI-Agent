"""
AutoSubmitter - 自动投递模块
使用 Playwright 实现浏览器自动化投递
"""
import asyncio
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext
from modules.models import JobPosition, Resume, ApplicationRecord
from utils.logger import log


class BaseSubmitter:
    """投递器基类"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """启动浏览器"""
        pass
    
    async def stop(self):
        """停止浏览器"""
        pass
    
    async def submit(self, job: JobPosition, resume: Resume) -> bool:
        """
        投递岗位
        
        Args:
            job: 目标岗位
            resume: 简历
        
        Returns:
            是否成功
        """
        raise NotImplementedError
    
    async def close(self):
        """关闭资源"""
        if self.browser:
            await self.browser.close()


class BossZhipinSubmitter(BaseSubmitter):
    """BOSS 直聘投递器"""
    
    def __init__(self, headless: bool = False):
        super().__init__()
        self.headless = headless
        self.login_required = True
    
    async def start(self):
        """启动浏览器并登录"""
        playwright = await async_playwright().start()
        
        # 配置浏览器选项
        browser_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox'
            ]
        }
        
        self.browser = await playwright.chromium.launch(**browser_options)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()
        
        # 设置页面尺寸
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 需要手动登录
        log.info("请手动在浏览器中完成登录，然后按回车继续...")
        input("按回车键继续...")
        
        log.success("登录成功！")
    
    async def stop(self):
        """停止浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def submit(self, job: JobPosition, resume: Resume) -> bool:
        """
        投递 BOSS 直聘岗位
        
        注意：这是一个示例实现，实际使用时需要根据网站最新结构调整选择器和逻辑
        """
        try:
            log.info(f"开始投递：{job.title} @ {job.company}")
            
            # 打开岗位页面
            await self.page.goto(job.url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # 等待页面加载
            
            # 检查是否需要登录
            if await self._is_login_required():
                log.warning("需要重新登录")
                return False
            
            # 点击投递按钮
            await self._click_apply_button()
            await asyncio.sleep(2)
            
            # 填写表单
            success = await self._fill_form(resume, job)
            
            if success:
                # 提交
                await self._submit_application()
                
                # 记录投递
                record = ApplicationRecord(
                    job_id=job.id,
                    job_title=job.title,
                    company=job.company,
                    resume_version="v1.0",
                    status="submitted",
                    message="投递成功",
                    submit_time=datetime.now()
                )
                
                log.success(f"投递成功：{job.title} @ {job.company}")
                return True
            else:
                log.error(f"投递失败：{job.title}")
                return False
                
        except Exception as e:
            log.error(f"投递异常：{str(e)}")
            return False
    
    async def _is_login_required(self) -> bool:
        """检查是否需要登录"""
        # 检查登录相关元素
        login_indicators = [
            '登录',
            'signin',
            'login'
        ]
        
        body_text = await self.page.content()
        for indicator in login_indicators:
            if indicator in body_text.lower():
                return True
        
        return False
    
    async def _click_apply_button(self):
        """点击投递按钮"""
        # 尝试多种选择器
        selectors = [
            'a[href*="apply"]',
            '.apply-btn',
            '[class*="apply"]',
            'button[class*="apply"]'
        ]
        
        for selector in selectors:
            try:
                button = self.page.locator(selector)
                if await button.is_visible(timeout=2000):
                    await button.click()
                    log.debug(f"找到投递按钮：{selector}")
                    return
            except:
                continue
        
        # 如果都没找到，尝试截图调试
        log.warning("未找到投递按钮，正在截图调试...")
        await self.page.screenshot(path="debug_apply.png")
    
    async def _fill_form(self, resume: Resume, job: JobPosition) -> bool:
        """填写申请表单"""
        try:
            # 基本信息
            await self._fill_field('input[name="name"]', resume.name)
            await self._fill_field('input[name="phone"]', resume.phone)
            await self._fill_field('input[name="email"]', resume.email)
            
            # 教育背景
            if resume.education:
                edu = resume.education[0]
                await self._fill_field('input[name="school"]', edu.get('school', ''))
                await self._fill_field('input[name="major"]', edu.get('major', ''))
                await self._fill_field('input[name="degree"]', edu.get('degree', ''))
            
            # 上传简历
            await self._upload_resume(resume)
            
            # 其他问题（如果有）
            await self._answer_questions(job)
            
            return True
            
        except Exception as e:
            log.error(f"填写表单失败：{str(e)}")
            return False
    
    async def _fill_field(self, selector: str, value: str):
        """填写字段"""
        try:
            field = self.page.locator(selector)
            if await field.is_visible(timeout=3000):
                await field.fill(value)
                log.debug(f"填写字段：{selector} = {value[:20]}...")
        except Exception as e:
            log.warning(f"填写字段失败 {selector}: {str(e)}")
    
    async def _upload_resume(self, resume: Resume):
        """上传简历"""
        try:
            # 查找文件上传控件
            file_input = self.page.locator('input[type="file"]')
            
            if await file_input.is_visible(timeout=3000):
                # 这里需要实际的简历文件路径
                # 暂时跳过
                log.info("跳过简历上传（需要配置简历文件路径）")
        except Exception as e:
            log.warning(f"上传简历失败：{str(e)}")
    
    async def _answer_questions(self, job: JobPosition):
        """回答附加问题"""
        try:
            # 检查是否有常见问题
            common_questions = {
                '期望薪资': str(job.salary_min),
                '到岗时间': '一周内',
                '工作类型': '实习' if job.is_intern else '全职'
            }
            
            for question, default_answer in common_questions.items():
                # 查找相关问题
                question_selector = f'text="{question}"'
                if await self.page.locator(question_selector).count() > 0:
                    # 填写答案
                    await self._fill_field(f'text="{question}" + following::input', default_answer)
                    
        except Exception as e:
            log.warning(f"回答问答失败：{str(e)}")
    
    async def _submit_application(self):
        """提交申请"""
        try:
            # 查找提交按钮
            submit_selectors = [
                'button[type="submit"]',
                '.submit-btn',
                '[class*="submit"]',
                'button[class*="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = self.page.locator(selector)
                    if await submit_btn.is_visible(timeout=3000):
                        await submit_btn.click()
                        log.debug(f"找到提交按钮：{selector}")
                        
                        # 等待提交结果
                        await asyncio.sleep(3)
                        
                        # 检查是否成功
                        success_indicators = ['成功', '已投递', '提交成功']
                        page_content = await self.page.content()
                        
                        for indicator in success_indicators:
                            if indicator in page_content:
                                log.success("申请提交成功！")
                                return
                        
                        break
                except:
                    continue
            
            log.warning("未找到提交按钮或提交未确认")
            
        except Exception as e:
            log.error(f"提交申请失败：{str(e)}")
    
    async def close(self):
        """关闭资源"""
        await self.stop()


class GeneralSubmitter(BaseSubmitter):
    """通用投递器 - 适用于各种招聘网站"""
    
    def __init__(self, headless: bool = False):
        super().__init__()
        self.headless = headless
    
    async def start(self):
        """启动浏览器"""
        playwright = await async_playwright().start()
        
        browser_options = {
            'headless': self.headless,
            'args': ['--disable-blink-features=AutomationControlled']
        }
        
        self.browser = await playwright.chromium.launch(**browser_options)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        
        log.info("通用投递器已启动")
    
    async def stop(self):
        """停止浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def submit(self, job: JobPosition, resume: Resume) -> bool:
        """
        通用投递方法
        
        注意：由于不同网站结构差异大，这里提供基础框架
        实际使用时需要根据具体网站定制
        """
        try:
            log.info(f"尝试投递：{job.title} @ {job.company}")
            
            # 打开页面
            await self.page.goto(job.apply_url or job.url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 尝试自动识别投递流程
            # 这部分需要根据具体网站实现
            
            log.warning("通用投递器需要针对具体网站定制")
            return False
            
        except Exception as e:
            log.error(f"通用投递失败：{str(e)}")
            return False
    
    async def close(self):
        """关闭资源"""
        await self.stop()


class AutoSubmitterManager:
    """自动投递管理器"""
    
    def __init__(self, auto_submit: bool = False, daily_limit: int = 50):
        """
        Args:
            auto_submit: 是否自动投递
            daily_limit: 每日投递上限
        """
        self.auto_submit = auto_submit
        self.daily_limit = daily_limit
        self.submitters = {
            'boss_zhipin': BossZhipinSubmitter(),
            'general': GeneralSubmitter()
        }
        self.daily_count = 0
        self.submitted_jobs = set()
    
    async def initialize(self):
        """初始化投递器"""
        if self.auto_submit:
            await self.submitters['boss_zhipin'].start()
            log.success("自动投递系统已初始化")
        else:
            log.info("自动投递功能已禁用，仅生成预览")
    
    async def submit_job(self, job: JobPosition, resume: Resume) -> bool:
        """
        投递单个岗位
        
        Args:
            job: 目标岗位
            resume: 简历
        
        Returns:
            是否成功
        """
        # 检查每日限制
        if self.daily_count >= self.daily_limit:
            log.warning(f"已达到每日投递上限 ({self.daily_limit})")
            return False
        
        # 检查是否已投递
        if job.id in self.submitted_jobs:
            log.debug(f"岗位已投递：{job.id}")
            return True
        
        # 选择投递器
        platform = job.platform
        submitter = self.submitters.get(platform, self.submitters['general'])
        
        # 执行投递
        if self.auto_submit:
            success = await submitter.submit(job, resume)
            
            if success:
                self.daily_count += 1
                self.submitted_jobs.add(job.id)
                
                # 记录投递
                record = ApplicationRecord(
                    job_id=job.id,
                    job_title=job.title,
                    company=job.company,
                    resume_version="v1.0",
                    status="success",
                    submit_time=datetime.now()
                )
                
                return True
        else:
            # 仅预览模式
            log.info(f"预览投递：{job.title} @ {job.company}")
            log.info(f"  城市：{job.city}")
            log.info(f"  薪资：{job.get_salary_range()}")
            log.info(f"  链接：{job.url}")
            
            self.submitted_jobs.add(job.id)
            return True
        
        return False
    
    async def batch_submit(self, jobs: List[JobPosition], 
                          resume: Resume,
                          max_concurrent: int = 3) -> Dict[str, int]:
        """
        批量投递
        
        Args:
            jobs: 岗位列表
            resume: 简历
            max_concurrent: 最大并发数
        
        Returns:
            统计结果
        """
        results = {
            'total': len(jobs),
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def submit_with_semaphore(job):
            async with semaphore:
                # 添加延迟避免触发反爬
                await asyncio.sleep(2)
                
                success = await self.submit_job(job, resume)
                
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                
                # 检查每日限制
                if self.daily_count >= self.daily_limit:
                    log.warning("达到每日投递上限，停止投递")
                    return False
                
                return success
        
        # 并发投递
        tasks = [submit_with_semaphore(job) for job in jobs]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        results['skipped'] = results['total'] - results['success'] - results['failed']
        
        log.info(f"批量投递完成：成功={results['success']}, 失败={results['failed']}, 跳过={results['skipped']}")
        
        return results
    
    async def shutdown(self):
        """关闭所有投递器"""
        for name, submitter in self.submitters.items():
            try:
                await submitter.close()
                log.debug(f"{name} 投递器已关闭")
            except Exception as e:
                log.error(f"关闭 {name} 投递器失败：{str(e)}")


# 导出常用类
__all__ = ['AutoSubmitterManager', 'BossZhipinSubmitter', 'GeneralSubmitter']
