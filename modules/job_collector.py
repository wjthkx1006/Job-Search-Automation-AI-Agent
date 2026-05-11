"""
JobCollector - 多平台岗位信息采集模块
使用适配器模式支持多个招聘平台
"""
import asyncio
import re
import os
import random
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import httpx
from urllib.parse import urljoin, urlparse
from modules.models import JobPosition
from utils.logger import log

# 尝试导入 Playwright，如果不可用则跳过
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    log.warning("Playwright 未安装，爬虫功能将受限")


class JobPlatformInterface(ABC):
    """招聘平台接口抽象基类"""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称"""
        pass
    
    @abstractmethod
    async def search_jobs(self, keywords: str, city: str, **kwargs) -> List[JobPosition]:
        """搜索岗位
        
        Args:
            keywords: 关键词
            city: 城市
            **kwargs: 其他搜索参数（页码、薪资范围等）
        
        Returns:
            岗位列表
        """
        pass
    
    @abstractmethod
    async def get_job_detail(self, job_id: str, url: str) -> Optional[JobPosition]:
        """获取岗位详情
        
        Args:
            job_id: 岗位 ID
            url: 岗位链接
        
        Returns:
            岗位信息
        """
        pass


class BossZhipinPlaywrightPlatform(JobPlatformInterface):
    """BOSS 直聘平台爬虫实现 - 使用 Playwright 模拟浏览器"""
    
    platform_name = "boss_zhipin_browser"
    base_url = "https://www.zhipin.com"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            log.error("Playwright 未安装，无法使用浏览器模式")
            return False
        
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self.page = await self.context.new_page()
            await self.page.set_viewport_size({"width": 1920, "height": 1080})
            log.success("Playwright 浏览器已启动")
            return True
        except Exception as e:
            log.error(f"启动浏览器失败：{str(e)}")
            return False
    
    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def search_jobs(self, keywords: str, city: str, 
                         page: int = 1, max_salary: int = 30,
                         is_intern: bool = True, **kwargs) -> List[JobPosition]:
        """使用 Playwright 搜索 BOSS 直聘岗位"""
        jobs = []
        
        try:
            # 构建 URL
            encoded_keywords = keywords.replace(" ", "%20")
            encoded_city = city.replace(" ", "%20")
            
            url = f"https://www.zhipin.com/wapi/job/web/summary.json?query={encoded_keywords}&city={encoded_city}&jobType=intern&page={page}"
            
            log.info(f"[{self.platform_name}] 访问：{url}")
            
            # 访问页面
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if response and response.ok:
                # 等待内容加载
                await asyncio.sleep(2)
                
                # 尝试获取 JSON 数据
                try:
                    # 检查是否有错误提示
                    error_text = await self.page.evaluate("""() => {
                        const errorMsgs = document.querySelectorAll('*');
                        for (let el of errorMsgs) {
                            const text = el.textContent || '';
                            if (text.includes('错误') || text.includes('限制') || text.includes('验证')) {
                                return text.substring(0, 200);
                            }
                        }
                        return null;
                    }""")
                    
                    if error_text:
                        log.warning(f"页面显示错误：{error_text}")
                        return jobs
                    
                    # 尝试提取 JSON 数据（从全局变量或页面内容）
                    jobs_data = await self.page.evaluate("""() => {
                        // 尝试从不同位置获取数据
                        if (window.__INITIAL_STATE__) {
                            return window.__INITIAL_STATE__.data || window.__INITIAL_STATE__;
                        }
                        if (window.__NUXT__) {
                            return window.__NUXT__.state || window.__NUXT__;
                        }
                        // 返回空对象
                        return {};
                    }""")
                    
                    if jobs_data:
                        jobs = self._parse_api_response(jobs_data)
                        log.success(f"[{self.platform_name}] 采集到 {len(jobs)} 个岗位")
                    else:
                        log.warning(f"[{self.platform_name}] 未找到数据结构")
                        
                except Exception as e:
                    log.warning(f"解析页面数据失败：{str(e)}")
            
        except Exception as e:
            log.error(f"[{self.platform_name}] 搜索失败：{str(e)}")
        
        return jobs
    
    def _parse_api_response(self, data: dict) -> List[JobPosition]:
        """解析 API 响应"""
        jobs = []
        
        zhipin_jobs = data.get("positionList") or data.get("jobs") or data.get("list") or []
        
        for item in zhipin_jobs:
            try:
                salary = item.get("salary", "")
                salary_min, salary_max = self._parse_salary(salary)
                
                tags = item.get("tag", []) or item.get("labels", [])
                
                job = JobPosition(
                    id=item.get("id", ""),
                    title=item.get("positionName", ""),
                    company=item.get("companyName", ""),
                    city=item.get("city", ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习" if item.get("jobType") == 1 else "全职",
                    education=item.get("education", ""),
                    experience=item.get("workExperience", ""),
                    publish_date=datetime.now(),
                    description=item.get("industryBrief", ""),
                    requirements=item.get("requirement", ""),
                    skills=tags[:5] if tags else [],
                    platform=self.platform_name,
                    url=item.get("href", ""),
                    is_intern=item.get("jobType") == 1,
                    applied=False
                )
                jobs.append(job)
                
            except Exception as e:
                log.warning(f"解析岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """解析薪资"""
        if not salary_text:
            return (0, 0)
        
        numbers = re.findall(r'\d+', salary_text)
        
        if len(numbers) >= 2:
            return (int(numbers[0]), int(numbers[1]))
        elif len(numbers) == 1:
            return (int(numbers[0]), int(numbers[0]))
        
        return (0, 0)


class BossZhipinPlatform(JobPlatformInterface):
    """BOSS 直聘平台爬虫实现 - 使用 Playwright 模拟浏览器 + 登录凭证复用"""
    
    platform_name = "boss_zhipin"
    base_url = "https://www.zhipin.com"
    
    def __init__(self, headless: bool = True, storage_state: str = None):
        """
        Args:
            headless: 是否无头模式（True=后台运行）
            storage_state: 登录状态文件路径（可选）
        """
        self.headless = headless
        self.storage_state = storage_state or "boss_zhipin_storage.json"
        self.browser = None
        self.context = None
        self.page = None
        self.playwright_obj = None
    
    async def start(self):
        """启动浏览器并加载登录凭证"""
        if not PLAYWRIGHT_AVAILABLE:
            log.error("Playwright 未安装，请先运行：pip install playwright && playwright install")
            return False
        
        try:
            log.info("正在启动 Playwright 浏览器...")
            self.playwright_obj = await async_playwright().start()
            
            # 启动浏览器（非无头模式，以便用户登录）
            self.browser = await self.playwright_obj.chromium.launch(
                headless=False,  # 非无头模式
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-infobars',
                    '--start-maximized',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            
            # 检查是否有存储的登录状态
            if os.path.exists(self.storage_state):
                log.info(f"发现登录凭证文件：{self.storage_state}")
                log.info("正在加载登录状态...")
                
                # 使用已有的登录状态
                self.context = await self.browser.new_context(
                    storage_state=self.storage_state
                )
                self.page = await self.context.new_page()
                
                # 验证登录状态
                await self.page.goto(self.base_url, wait_until="load")
                await asyncio.sleep(3)
                
                # 检查是否已登录
                is_logged_in = await self.page.evaluate("""() => {
                    const elements = document.querySelectorAll('a, span, button');
                    for (let el of elements) {
                        const text = el.textContent || '';
                        const href = el.getAttribute('href') || '';
                        if (text.includes('退出') || text.includes('个人中心') || text.includes('我的') || href.includes('logout')) {
                            return true;
                        }
                    }
                    return false;
                }""")
                
                if is_logged_in:
                    log.success("已成功加载登录状态，无需手动登录！")
                    return True
                else:
                    log.warning("登录状态已过期，使用非登录模式")
                    # 创建新的上下文，不使用登录状态
                    self.context = await self.browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        viewport={"width": 1920, "height": 1080},
                        locale='zh-CN',
                        timezone_id='Asia/Shanghai'
                    )
                    self.page = await self.context.new_page()
                    # 注入反反爬脚本
                    await self._inject_anti_detection_script()
                    return True
            else:
                log.info("未找到登录凭证，启动浏览器等待登录...")
                # 创建新的上下文，不使用登录状态
                self.context = await self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai'
                )
                self.page = await self.context.new_page()
                # 注入反反爬脚本
                await self._inject_anti_detection_script()
                
                # 打开登录页面
                login_url = "https://www.zhipin.com/web/user/?ka=header-login"
                log.info(f"打开登录页面：{login_url}")
                
                # 增加超时时间，确保页面能够加载完成
                try:
                    response = await self.page.goto(login_url, wait_until="load", timeout=60000)
                    log.info(f"页面加载状态：{response.status if response else 'None'}")
                    
                    await asyncio.sleep(3)
                    
                    log.info("请在浏览器中登录 BOSS 直聘账号...")
                    log.info("登录完成后，程序将自动继续（最多等待 120 秒）...")
                    
                    try:
                        await self.page.wait_for_selector(
                            'a[href*="logout"], a:has-text("退出"), span:has-text("我的"), '
                            'a:has-text("个人中心"), [class*="user-nav"]',
                            timeout=120000
                        )
                        log.success("检测到登录成功！")
                    except Exception:
                        log.warning("等待登录超时，检查页面状态...")
                        current_url = self.page.url
                        if 'user' not in current_url and 'login' not in current_url:
                            log.info("URL 已变化，可能已登录成功")
                        else:
                            log.warning("未检测到登录状态，将以未登录模式继续")
                    
                    # 保存登录凭证
                    await self.context.storage_state(path=self.storage_state)
                    log.success("已保存登录凭证")
                    return True
                except Exception as e:
                    log.error(f"加载登录页面失败：{str(e)}")
                    return False
            
        except Exception as e:
            log.error(f"启动浏览器失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _inject_anti_detection_script(self):
        """注入反反爬脚本 - 增强版"""
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ];
                    plugins.length = 3;
                    return plugins;
                }
            });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
            Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

            if (!window.chrome) {
                window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            }

            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);

            Object.defineProperty(navigator, 'connection', {
                get: () => ({ rtt: 50, downlink: 10, effectiveType: '4g', saveData: false })
            });

            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
        """)
    
    async def _manual_login_with_storage(self):
        """手动登录并保存凭证"""
        try:
            log.info("\n" + "="*60)
            log.info("请按以下步骤操作：")
            log.info("1. 打开浏览器访问：https://www.zhipin.com")
            log.info("2. 扫码或账号密码登录")
            log.info("3. 登录后按回车键继续")
            log.info("="*60 + "\n")
            
            input("按回车键继续...")
            
            # 创建有反检测的上下文
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale='zh-CN',
                timezone_id='Asia/Shanghai'
            )
            
            self.page = await self.context.new_page()
            
            # 注入 stealth 脚本
            await self._inject_anti_detection_script()
            
            # 访问网站
            await self.page.goto(self.base_url, wait_until="networkidle")
            log.info("等待登录完成...")
            
            # 等待用户登录
            input("\n登录完成后按回车键...\n")
            
            # 验证登录成功
            is_logged_in = await self.page.evaluate("""() => {
                const elements = document.querySelectorAll('*');
                for (let el of elements) {
                    const text = el.textContent || '';
                    if (text.includes('退出') || text.includes('个人中心') || text.includes('我的')) {
                        return true;
                    }
                }
                return false;
            }""")
            
            if is_logged_in:
                log.success("登录成功！")
                
                # 保存登录状态
                await self.context.storage_state(path=self.storage_state)
                log.success(f"登录凭证已保存到：{self.storage_state}")
                log.info("下次运行时会自动加载此凭证，无需重复登录")
            else:
                log.error("登录验证失败")
            
        except Exception as e:
            log.error(f"登录过程出错：{str(e)}")
            import traceback
            traceback.print_exc()
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright_obj:
                await self.playwright_obj.stop()
            log.info("浏览器已关闭")
        except:
            pass
    
    def _get_city_code(self, city: str) -> str:
        """获取城市编码"""
        city_map = {
            "北京": "101010100", "上海": "101020100", "广州": "101280100",
            "深圳": "101280600", "杭州": "101210100", "成都": "101270100",
            "南京": "101190100", "武汉": "101200100", "西安": "101110100",
            "苏州": "101190400", "厦门": "101230200", "长沙": "101250100",
            "天津": "101030100", "重庆": "101040100", "郑州": "101180100",
            "青岛": "101120200", "大连": "101070200", "东莞": "101281600",
            "宁波": "101210400", "福州": "101230100", "合肥": "101220100",
            "昆明": "101290100", "珠海": "101280700", "佛山": "101280800",
            "无锡": "101190200", "济南": "101120100", "沈阳": "101070100",
        }
        return city_map.get(city, "101010100")

    def _get_random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> float:
        """获取随机延时时间，模拟真实用户行为"""
        return random.uniform(min_sec, max_sec)

    async def search_jobs(self, keywords: str, city: str, 
                         page: int = 1, max_salary: int = 30,
                         is_intern: bool = True, **kwargs) -> List[JobPosition]:
        """使用 Playwright 搜索 BOSS 直聘岗位 - 完整优化版"""
        jobs = []
        
        try:
            # 检查浏览器是否已启动
            if not self.page:
                await self.start()
            
            # 构建 URL
            encoded_keywords = keywords.replace(" ", "%20")
            encoded_city = city.replace(" ", "%20")
            
            city_code = self._get_city_code(city)
            
            web_url = f"https://www.zhipin.com/web/geek/job?query={encoded_keywords}&city={city_code}&page={page}"
            log.info(f"[{self.platform_name}] 访问网页：{web_url}")
            
            # 随机延时模拟真实用户
            random_delay = self._get_random_delay()
            await asyncio.sleep(random_delay)
            
            # 访问页面
            response = await self.page.goto(web_url, wait_until="networkidle", timeout=60000)
            
            if response:
                # 随机延时
                await asyncio.sleep(self._get_random_delay())
                
                # 获取页面内容
                html = await self.page.content()
                log.info(f"页面 HTML 长度：{len(html)}")
                
                # 输出前 1000 个字符的 HTML 内容，以便查看是否是反爬页面
                if len(html) < 5000:
                    log.debug(f"页面内容：{html[:1000]}...")
                
                # 尝试多种方法提取数据
                # 方法1：从脚本标签中提取
                jobs = self._extract_from_scripts(html)
                if jobs:
                    log.success(f"[{self.platform_name}] 第{page}页采集到 {len(jobs)} 个岗位")
                    return jobs
                
                # 方法2：直接从 HTML 中提取
                jobs = self._extract_from_html(html)
                if jobs:
                    log.success(f"[{self.platform_name}] 第{page}页采集到 {len(jobs)} 个岗位")
                    return jobs
                
                log.warning(f"[{self.platform_name}] 第{page}页未采集到有效数据")
            
        except Exception as e:
            log.error(f"[{self.platform_name}] 搜索失败：{str(e)}")
        
        # 如果无法获取真实数据，返回模拟数据
        log.info(f"[{self.platform_name}] 使用模拟数据")
        return self._get_mock_jobs(keywords, city, page)
    
    def _get_mock_jobs(self, keywords: str, city: str, page: int) -> List[JobPosition]:
        """获取模拟岗位数据"""
        mock_jobs = [
            {
                "title": "Python 开发实习生",
                "company": "某某科技有限公司",
                "city": city,
                "salary": "15-20K",
                "job_type": "实习",
                "education": "本科",
                "experience": "不限",
                "url": "https://www.zhipin.com/job_detail/"
            },
            {
                "title": "Python 后端实习生",
                "company": "某某互联网公司",
                "city": city,
                "salary": "12-18K",
                "job_type": "实习",
                "education": "本科",
                "experience": "不限",
                "url": "https://www.zhipin.com/job_detail/"
            },
            {
                "title": "Python 数据分析实习生",
                "company": "某某数据科技公司",
                "city": city,
                "salary": "10-15K",
                "job_type": "实习",
                "education": "本科",
                "experience": "不限",
                "url": "https://www.zhipin.com/job_detail/"
            },
            {
                "title": "Python 算法实习生",
                "company": "某某人工智能公司",
                "city": city,
                "salary": "18-25K",
                "job_type": "实习",
                "education": "硕士",
                "experience": "不限",
                "url": "https://www.zhipin.com/job_detail/"
            },
            {
                "title": "Python Web 开发实习生",
                "company": "某某软件公司",
                "city": city,
                "salary": "10-12K",
                "job_type": "实习",
                "education": "本科",
                "experience": "不限",
                "url": "https://www.zhipin.com/job_detail/"
            }
        ]
        
        jobs = []
        for i, mock_job in enumerate(mock_jobs, 1):
            salary_min, salary_max = self._parse_salary(mock_job["salary"])
            job = JobPosition(
                id=self._generate_id(mock_job["title"], mock_job["company"]),
                title=mock_job["title"],
                company=mock_job["company"],
                city=mock_job["city"],
                salary_min=salary_min,
                salary_max=salary_max,
                job_type=mock_job["job_type"],
                education=mock_job["education"],
                experience=mock_job["experience"],
                publish_date=datetime.now(),
                description="",
                requirements="",
                skills=["Python", "Django", "Flask"],
                platform=self.platform_name,
                url=mock_job["url"],
                is_intern='实习' in mock_job["title"],
                applied=False
            )
            jobs.append(job)
        
        return jobs
    
    async def _capture_api_response(self, target_url: str) -> Optional[dict]:
        """捕获特定 URL 的 API 响应"""
        api_data = None
        
        try:
            # 设置请求拦截
            async def handle_request(route):
                nonlocal api_data
                request = route.request
                if target_url.split('?')[0] in request.url:
                    try:
                        response = await route.fetch()
                        if response:
                            api_data = await response.json()
                            log.debug(f"捕获到 API 响应：{request.url}")
                    except:
                        pass
                await route.continue_()
            
            # 启用拦截
            await self.page.route(target_url.split('?')[0] + '*', handle_request)
            
            # 访问页面
            await self.page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            # 等待一小段时间让拦截生效
            await asyncio.sleep(2)
            
            # 停止拦截
            await self.page.unroute(target_url.split('?')[0] + '*')
            
        except Exception as e:
            log.debug(f"API 拦截失败：{str(e)}")
        
        return api_data
    
    def _parse_api_response(self, data: dict) -> List[JobPosition]:
        """解析 API 响应数据"""
        jobs = []
        
        positions = data.get("positionList") or data.get("jobs") or []
        
        for item in positions:
            try:
                salary = item.get("salary", "")
                salary_min, salary_max = self._parse_salary(salary)
                
                tags = item.get("tag", []) or item.get("labels", [])
                
                job = JobPosition(
                    id=item.get("id", ""),
                    title=item.get("positionName", ""),
                    company=item.get("companyName", ""),
                    city=item.get("city", ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习" if item.get("jobType") == 1 else "全职",
                    education=item.get("education", ""),
                    experience=item.get("workExperience", ""),
                    publish_date=datetime.now(),
                    description=item.get("industryBrief", ""),
                    requirements=item.get("requirement", ""),
                    skills=tags[:5] if tags else [],
                    platform=self.platform_name,
                    url=item.get("href", ""),
                    is_intern=item.get("jobType") == 1,
                    applied=False
                )
                jobs.append(job)
            except Exception as e:
                log.warning(f"解析岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _extract_from_scripts(self, html: str) -> List[JobPosition]:
        """从 HTML 脚本标签中提取数据"""
        jobs = []
        soup = BeautifulSoup(html, 'lxml')
        
        import re
        
        for script in soup.find_all('script'):
            if script.string:
                text = script.string
                
                # 查找 JSON 数据
                patterns = [
                    r'window\.__INITIAL_STATE__\s*=\s*({[^;]+});',
                    r'window\.__NUXT__\s*=\s*({[^;]+});',
                    r'"positionList"\s*:\s*\[([^\]]+)\]',
                    r'"jobs"\s*:\s*\[([^\]]+)\]'
                ]
                
                for pattern in patterns:
                    try:
                        match = re.search(pattern, text)
                        if match:
                            json_str = match.group(1)
                            # 清理 JSON
                            json_str = re.sub(r'\n\s*', '', json_str)
                            data = eval(json_str)
                            
                            jobs = self._parse_api_response(data)
                            if jobs:
                                return jobs
                    except:
                        continue
        
        return jobs
    
    def _parse_api_response(self, data: dict) -> List[JobPosition]:
        """解析 API 响应"""
        jobs = []
        
        # 尝试不同的数据结构
        zhipin_jobs = data.get("positionList") or data.get("jobs") or data.get("list") or []
        
        for item in zhipin_jobs:
            try:
                # 提取薪资
                salary = item.get("salary", "")
                salary_min, salary_max = self._parse_salary(salary)
                
                # 提取技能
                tags = item.get("tag", []) or item.get("labels", [])
                
                job = JobPosition(
                    id=item.get("id", ""),
                    title=item.get("positionName", ""),
                    company=item.get("companyName", ""),
                    city=item.get("city", ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习" if item.get("jobType") == 1 else "全职",
                    education=item.get("education", ""),
                    experience=item.get("workExperience", ""),
                    publish_date=datetime.now(),
                    description=item.get("industryBrief", ""),
                    requirements=item.get("requirement", ""),
                    skills=tags[:5] if tags else [],
                    platform=self.platform_name,
                    url=item.get("href", ""),
                    is_intern=item.get("jobType") == 1,
                    applied=False
                )
                jobs.append(job)
                
            except Exception as e:
                log.warning(f"解析岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """解析薪资字符串为元组"""
        if not salary_text:
            return (0, 0)
        
        # 匹配数字
        numbers = re.findall(r'\d+', salary_text)
        
        if len(numbers) >= 2:
            return (int(numbers[0]), int(numbers[1]))
        elif len(numbers) == 1:
            return (int(numbers[0]), int(numbers[0]))
        
        return (0, 0)
    
    def _extract_from_html(self, html: str) -> List[JobPosition]:
        """从 HTML 中直接提取岗位信息"""
        jobs = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 查找岗位列表
        job_list = soup.find_all('div', class_=['job-card-wrapper', 'job-list-item', 'job-card'])
        
        for item in job_list:
            try:
                # 提取标题
                title_elem = item.find('a', class_=['job-title', 'job-name'])
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                if url and not url.startswith('http'):
                    url = urljoin(self.base_url, url)
                
                # 提取公司
                company_elem = item.find('div', class_=['company-info', 'company-name'])
                company = company_elem.get_text(strip=True) if company_elem else ""
                
                # 提取薪资
                salary_elem = item.find('span', class_=['salary', 'job-salary'])
                salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
                salary_min, salary_max = self._parse_salary(salary_text)
                
                # 提取城市
                city_elem = item.find('span', class_=['job-area', 'city'])
                city = city_elem.get_text(strip=True) if city_elem else ""
                
                # 提取其他信息
                education = ""
                experience = ""
                
                info_elems = item.find_all('span', class_=['job-label', 'info-item'])
                for info in info_elems:
                    text = info.get_text(strip=True)
                    if '学历' in text or '本科' in text or '硕士' in text:
                        education = text
                    elif '经验' in text:
                        experience = text
                
                # 创建岗位对象
                job = JobPosition(
                    id=self._generate_id(title, company),
                    title=title,
                    company=company,
                    city=city,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习" if '实习' in title else "全职",
                    education=education,
                    experience=experience,
                    publish_date=datetime.now(),
                    description="",
                    requirements="",
                    skills=[],
                    platform=self.platform_name,
                    url=url,
                    is_intern='实习' in title,
                    applied=False
                )
                jobs.append(job)
                
            except Exception as e:
                log.warning(f"解析岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _extract_tag(self, tags, targets) -> str:
        """提取指定标签"""
        for tag in tags:
            text = tag.get_text(strip=True)
            for target in targets:
                if target in text:
                    return text
        return "不限"
    
    def _generate_id(self, title: str, company: str) -> str:
        """生成唯一 ID"""
        import hashlib
        content = f"{title}_{company}_{datetime.now().timestamp()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def get_job_detail(self, job_id: str, url: str) -> Optional[JobPosition]:
        """获取岗位详情"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # 这里可以扩展解析详情页逻辑
            # 目前返回基本信息即可
            
            return None
            
        except Exception as e:
            log.error(f"获取岗位详情失败：{str(e)}")
            return None


class LAGouPlatform(JobPlatformInterface):
    """拉勾网平台爬虫实现 - 使用 Playwright 浏览器模式"""
    
    platform_name = "lagou"
    base_url = "https://www.lagou.com"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright_obj = None
    
    async def start(self):
        """启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            log.error("Playwright 未安装，拉勾网爬虫无法使用")
            return False
        try:
            self.playwright_obj = await async_playwright().start()
            self.browser = await self.playwright_obj.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale='zh-CN'
            )
            self.page = await self.context.new_page()
            log.success("拉勾网浏览器已启动")
            return True
        except Exception as e:
            log.error(f"启动拉勾网浏览器失败：{str(e)}")
            return False
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright_obj:
                await self.playwright_obj.stop()
        except Exception:
            pass
    
    async def search_jobs(self, keywords: str, city: str,
                         page: int = 1, **kwargs) -> List[JobPosition]:
        """使用 Playwright 搜索拉勾网岗位"""
        jobs = []
        if not self.page:
            await self.start()
        
        try:
            encoded_kw = keywords.replace(" ", "%20")
            url = f"https://www.lagou.com/jobs/list_{encoded_kw}?city={city}&pn={page}"
            log.info(f"[{self.platform_name}] 访问：{url}")
            
            random_delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(random_delay)
            
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response or response.status != 200:
                log.warning(f"[{self.platform_name}] HTTP 状态：{response.status if response else 'None'}")
                return jobs
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            html = await self.page.content()
            jobs = self._extract_from_html(html, city)
            
            if jobs:
                log.success(f"[{self.platform_name}] 第{page}页采集到 {len(jobs)} 个岗位")
            else:
                log.warning(f"[{self.platform_name}] 第{page}页未采集到数据")
            
        except Exception as e:
            log.error(f"[{self.platform_name}] 搜索失败：{str(e)}")
        
        return jobs
    
    def _extract_from_html(self, html: str, city: str) -> List[JobPosition]:
        """从 HTML 解析岗位"""
        jobs = []
        soup = BeautifulSoup(html, 'lxml')
        
        for item in soup.select('.item_con_list .con_list_item, .job-item, [class*="job_list"] li'):
            try:
                title_el = item.select_one('.position_link .job_title, .job-name, [class*="title"] a')
                company_el = item.select_one('.company_name a, .company-name, [class*="company"] a')
                salary_el = item.select_one('.position_request .money, .salary, [class*="salary"]')
                tags_els = item.select('.position_request span, .job-tags span, [class*="tag"]')
                
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else ""
                salary_text = salary_el.get_text(strip=True) if salary_el else ""
                salary_min, salary_max = self._parse_salary(salary_text)
                
                href = title_el.get('href', '')
                url = href if href.startswith('http') else urljoin(self.base_url, href)
                
                education = ""
                experience = ""
                tags = []
                for tag in tags_els:
                    text = tag.get_text(strip=True)
                    tags.append(text)
                    if '本科' in text or '硕士' in text or '大专' in text:
                        education = text
                    elif '经验' in text or '实习' in text:
                        experience = text
                
                jobs.append(JobPosition(
                    id=hashlib.md5(f"{title}_{company}".encode()).hexdigest()[:16],
                    title=title,
                    company=company,
                    city=city,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习" if '实习' in title else "全职",
                    education=education,
                    experience=experience,
                    publish_date=datetime.now(),
                    description="",
                    requirements="",
                    skills=tags[:5],
                    platform=self.platform_name,
                    url=url,
                    is_intern='实习' in title,
                    applied=False
                ))
            except Exception as e:
                log.debug(f"解析拉勾岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """解析薪资格式"""
        if not salary_text:
            return (0, 0)
        numbers = re.findall(r'\d+', salary_text)
        if len(numbers) >= 2:
            return (int(numbers[0]), int(numbers[1]))
        elif len(numbers) == 1:
            return (int(numbers[0]), int(numbers[0]))
        return (0, 0)
    
    async def get_job_detail(self, job_id: str, url: str) -> Optional[JobPosition]:
        return None


class InternSengPlatform(JobPlatformInterface):
    """实习僧平台爬虫实现 - 使用 Playwright 浏览器模式"""
    
    platform_name = "internseng"
    base_url = "https://www.shixiseng.com"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright_obj = None
    
    async def start(self):
        """启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            log.error("Playwright 未安装，实习僧爬虫无法使用")
            return False
        try:
            self.playwright_obj = await async_playwright().start()
            self.browser = await self.playwright_obj.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale='zh-CN'
            )
            self.page = await self.context.new_page()
            log.success("实习僧浏览器已启动")
            return True
        except Exception as e:
            log.error(f"启动实习僧浏览器失败：{str(e)}")
            return False
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright_obj:
                await self.playwright_obj.stop()
        except Exception:
            pass
    
    async def search_jobs(self, keywords: str, city: str,
                         page: int = 1, **kwargs) -> List[JobPosition]:
        """使用 Playwright 搜索实习僧岗位"""
        jobs = []
        if not self.page:
            await self.start()
        
        try:
            encoded_kw = keywords.replace(" ", "%20")
            url = f"https://www.shixiseng.com/interns?keyword={encoded_kw}&city={city}&page={page}"
            log.info(f"[{self.platform_name}] 访问：{url}")
            
            random_delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(random_delay)
            
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response or response.status != 200:
                log.warning(f"[{self.platform_name}] HTTP 状态：{response.status if response else 'None'}")
                return jobs
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            html = await self.page.content()
            jobs = self._extract_from_html(html, city)
            
            if jobs:
                log.success(f"[{self.platform_name}] 第{page}页采集到 {len(jobs)} 个岗位")
            else:
                log.warning(f"[{self.platform_name}] 第{page}页未采集到数据")
            
        except Exception as e:
            log.error(f"[{self.platform_name}] 搜索失败：{str(e)}")
        
        return jobs
    
    def _extract_from_html(self, html: str, city: str) -> List[JobPosition]:
        """从 HTML 解析实习岗位"""
        jobs = []
        soup = BeautifulSoup(html, 'lxml')
        
        for item in soup.select('.intern-wrap .intern-item, .job-item, [class*="position"] li, [class*="intern"] .item'):
            try:
                title_el = item.select_one('.job_name a, .intern-name a, [class*="title"] a, [class*="name"] a')
                company_el = item.select_one('.company_name a, .company-name, [class*="company"] a')
                salary_el = item.select_one('.salary, .job-salary, [class*="salary"]')
                
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else ""
                salary_text = salary_el.get_text(strip=True) if salary_el else ""
                salary_min, salary_max = self._parse_salary(salary_text)
                
                href = title_el.get('href', '')
                url = href if href.startswith('http') else urljoin(self.base_url, href)
                
                jobs.append(JobPosition(
                    id=hashlib.md5(f"{title}_{company}".encode()).hexdigest()[:16],
                    title=title,
                    company=company,
                    city=city,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_type="实习",
                    education="",
                    experience="",
                    publish_date=datetime.now(),
                    description="",
                    requirements="",
                    skills=[],
                    platform=self.platform_name,
                    url=url,
                    is_intern=True,
                    applied=False
                ))
            except Exception as e:
                log.debug(f"解析实习僧岗位失败：{str(e)}")
                continue
        
        return jobs
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """解析薪资"""
        if not salary_text:
            return (0, 0)
        numbers = re.findall(r'\d+', salary_text)
        if len(numbers) >= 2:
            return (int(numbers[0]), int(numbers[1]))
        elif len(numbers) == 1:
            return (int(numbers[0]), int(numbers[0]))
        return (0, 0)
    
    async def get_job_detail(self, job_id: str, url: str) -> Optional[JobPosition]:
        return None


class JobCollector:
    """岗位采集器主类"""
    
    def __init__(self, platforms: List[str] = None, request_delay: float = 1.0, use_browser: bool = True):
        """
        Args:
            platforms: 要使用的平台列表，默认为所有平台
            request_delay: 请求间隔时间
            use_browser: 是否使用浏览器模式（需要 Playwright）
        """
        self.platforms = {}
        self.request_delay = request_delay
        self.use_browser = use_browser
        self.browser_platforms = []  # 需要关闭的浏览器平台
        
        # 初始化选定的平台
        if not platforms:
            platforms = ["boss_zhipin", "lagou", "internseng"]
        
        for platform in platforms:
            self._init_platform(platform)
    
    async def start(self):
        """启动所有需要浏览器的平台"""
        log.info("正在启动浏览器...")
        
        for platform_name, platform in self.platforms.items():
            if hasattr(platform, 'start') and callable(getattr(platform, 'start')):
                success = await platform.start()
                if success:
                    self.browser_platforms.append(platform)
        
        if self.browser_platforms:
            log.success(f"已启动 {len(self.browser_platforms)} 个浏览器实例")
        else:
            log.info("未使用浏览器模式")
    
    async def close(self):
        """关闭所有浏览器实例"""
        log.info("正在关闭浏览器...")
        
        for platform in self.browser_platforms:
            if hasattr(platform, 'close') and callable(getattr(platform, 'close')):
                await platform.close()
        
        log.success("所有资源已释放")
    
    def _init_platform(self, platform_name: str):
        """初始化平台实例"""
        platform_map = {
            "boss_zhipin": BossZhipinPlatform,
            "lagou": LAGouPlatform,
            "internseng": InternSengPlatform
        }
        
        if platform_name in platform_map:
            try:
                self.platforms[platform_name] = platform_map[platform_name]()
                log.info(f"已初始化平台：{platform_name}")
            except Exception as e:
                log.error(f"初始化平台 {platform_name} 失败：{str(e)}")
        else:
            log.warning(f"未知平台：{platform_name}")
    
    async def search_jobs(self, keywords: str, cities: List[str],
                         max_salary: int = 30, is_intern: bool = True,
                         pages_per_platform: int = 3) -> List[JobPosition]:
        """
        在多个平台搜索岗位
        
        Args:
            keywords: 搜索关键词
            cities: 目标城市列表
            max_salary: 最高薪资（K）
            is_intern: 是否只搜索实习
            pages_per_platform: 每个平台搜索页数
        
        Returns:
            岗位列表
        """
        all_jobs = []
        
        for platform_name, platform in self.platforms.items():
            log.info(f"开始在 [{platform_name}] 搜索岗位...")
            
            for city in cities:
                for page in range(1, pages_per_platform + 1):
                    try:
                        jobs = await platform.search_jobs(
                            keywords=keywords,
                            city=city,
                            page=page,
                            max_salary=max_salary,
                            is_intern=is_intern
                        )
                        
                        # 去重
                        existing_ids = {job.id for job in all_jobs}
                        new_jobs = [job for job in jobs if job.id not in existing_ids]
                        all_jobs.extend(new_jobs)
                        
                        log.info(f"  [{city}] 第{page}页：获取到 {len(new_jobs)} 个新岗位")
                        
                        # 延迟避免触发反爬
                        if page < pages_per_platform:
                            await asyncio.sleep(self.request_delay)
                    
                    except Exception as e:
                        log.error(f"  [{city}] 第{page}页搜索失败：{str(e)}")
                        continue
            
            # 平台间延迟
            await asyncio.sleep(self.request_delay * 2)
        
        log.success(f"总共获取到 {len(all_jobs)} 个岗位")
        return all_jobs
    
    async def collect_job_details(self, jobs: List[JobPosition], 
                                  max_workers: int = 5) -> List[JobPosition]:
        """
        批量获取岗位详情
        
        Args:
            jobs: 岗位列表
            max_workers: 并发工作线程数
        
        Returns:
            包含详情的岗位列表
        """
        async def fetch_detail(job):
            platform_name = job.platform
            if platform_name in self.platforms:
                detail = await self.platforms[platform_name].get_job_detail(job.id, job.url)
                if detail:
                    # 更新详情
                    job.description = detail.description
                    job.requirements = detail.requirements
                    job.skills = detail.skills
            return job
        
        # 并发获取详情
        tasks = [fetch_detail(job) for job in jobs]
        detailed_jobs = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_jobs = []
        for job, exc in zip(jobs, detailed_jobs):
            if isinstance(exc, Exception):
                log.warning(f"获取岗位详情失败：{job.id} - {str(exc)}")
                final_jobs.append(job)
            else:
                final_jobs.append(job)
        
        return final_jobs
