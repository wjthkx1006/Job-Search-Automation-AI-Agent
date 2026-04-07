"""
JobFilter - 智能岗位筛选模块
结合规则引擎和语义匹配进行岗位筛选
"""
import re
from typing import List, Dict, Optional, Set
from datetime import datetime
from modules.models import JobPosition
from utils.logger import log


class RuleEngine:
    """规则引擎 - 基于硬条件筛选"""
    
    def __init__(self, 
                 cities: List[str] = None,
                 min_salary: int = 0,
                 max_salary: int = 50000,
                 job_types: List[str] = None,
                 education: List[str] = None,
                 experience: List[str] = None):
        """
        Args:
            cities: 目标城市列表
            min_salary: 最低薪资（元/月）
            max_salary: 最高薪资（元/月）
            job_types: 工作类型（实习/全职）
            education: 学历要求
            experience: 经验要求
        """
        self.cities = set(cities or [])
        self.min_salary = min_salary
        self.max_salary = max_salary
        self.job_types = set(job_types or [])
        self.education = set(education or [])
        self.experience = set(experience or [])
        
        # 薪资转换：K 转元
        self.salary_threshold = min_salary * 1000 if min_salary > 0 else 0
    
    def filter(self, jobs: List[JobPosition]) -> List[JobPosition]:
        """
        应用规则筛选
        
        Args:
            jobs: 待筛选岗位列表
        
        Returns:
            筛选后的岗位列表
        """
        filtered_jobs = []
        
        for job in jobs:
            if self._apply_rules(job):
                filtered_jobs.append(job)
                log.debug(f"通过规则筛选：{job.title} @ {job.company}")
            else:
                log.debug(f"未通过规则筛选：{job.title} @ {job.company}")
        
        log.info(f"规则筛选后剩余 {len(filtered_jobs)} / {len(jobs)} 个岗位")
        return filtered_jobs
    
    def _apply_rules(self, job: JobPosition) -> bool:
        """应用所有规则检查单个岗位"""
        checks = [
            self._check_city,
            self._check_salary,
            self._check_job_type,
            self._check_education,
            self._check_experience
        ]
        
        return all(check(job) for check in checks)
    
    def _check_city(self, job: JobPosition) -> bool:
        """城市筛选"""
        if not self.cities:
            return True
        return job.city in self.cities
    
    def _check_salary(self, job: JobPosition) -> bool:
        """薪资筛选"""
        if self.salary_threshold == 0 and self.max_salary == 50000:
            return True
        
        # 使用最低薪资判断
        salary_min = job.salary_min * 1000 if job.salary_min > 0 else 0
        salary_max = job.salary_max * 1000 if job.salary_max > 0 else 0
        
        # 只要最低薪资满足条件即可
        return salary_min >= self.salary_threshold and salary_max <= self.max_salary
    
    def _check_job_type(self, job: JobPosition) -> bool:
        """工作类型筛选"""
        if not self.job_types:
            return True
        return job.job_type in self.job_types
    
    def _check_education(self, job: JobPosition) -> bool:
        """学历筛选"""
        if not self.education:
            return True
        
        # 简化处理：如果设置了教育要求，需要匹配
        edu_map = {
            '本科': ['本科'],
            '硕士': ['硕士', '博士'],
            '大专': ['大专'],
            '不限': ['不限']
        }
        
        required_edu = list(self.education)[0] if self.education else None
        if not required_edu:
            return True
        
        job_edu = job.education.lower()
        if '不限' in job_edu:
            return True
        
        if required_edu in job_edu:
            return True
        
        return False
    
    def _check_experience(self, job: JobPosition) -> bool:
        """经验筛选"""
        if not self.experience:
            return True
        
        # 简化处理
        return True


class SemanticMatcher:
    """语义匹配器 - 基于关键词和向量相似度"""
    
    def __init__(self):
        self.keyword_weights = {
            '技能关键词': 0.4,
            '专业关键词': 0.3,
            '软性要求': 0.2,
            '加分项': 0.1
        }
    
    def match(self, job: JobPosition, resume_skills: List[str],
              resume_keywords: List[str]) -> float:
        """
        计算岗位与简历的匹配度
        
        Args:
            job: 岗位信息
            resume_skills: 简历技能列表
            resume_keywords: 简历关键词列表
        
        Returns:
            匹配度分数 (0-100)
        """
        scores = []
        
        # 1. 技能匹配度
        skill_score = self._calculate_skill_match(job, resume_skills)
        scores.append(('技能匹配', skill_score, self.keyword_weights['技能关键词']))
        
        # 2. 关键词覆盖度
        keyword_score = self._calculate_keyword_coverage(job, resume_keywords)
        scores.append(('关键词覆盖', keyword_score, self.keyword_weights['专业关键词']))
        
        # 3. JD 解析质量
        jd_quality = self._evaluate_jd_quality(job)
        scores.append(('JD 质量', jd_quality, self.keyword_weights['软性要求']))
        
        # 4. 综合评分
        total_score = sum(score * weight for _, score, weight in scores)
        
        # 记录详细得分
        job.match_details = {
            'skills': scores[0],
            'keywords': scores[1],
            'jd_quality': scores[2],
            'total': total_score
        }
        
        return total_score
    
    def _calculate_skill_match(self, job: JobPosition, resume_skills: List[str]) -> float:
        """计算技能匹配度"""
        if not resume_skills:
            return 0
        
        # 提取 JD 中的技能关键词
        jd_skills = self._extract_skills_from_jd(job)
        
        if not jd_skills:
            return 50  # 无法提取技能时给中等分数
        
        # 计算匹配比例
        matched_skills = []
        for skill in resume_skills:
            for jd_skill in jd_skills:
                if self._is_similar(skill, jd_skill):
                    matched_skills.append(skill)
                    break
        
        match_ratio = len(matched_skills) / len(jd_skills)
        return min(match_ratio * 100, 100)
    
    def _extract_skills_from_jd(self, job: JobPosition) -> List[str]:
        """从 JD 中提取技能关键词"""
        skills = []
        text = job.description + job.requirements
        
        # 常见技能关键词模式
        skill_patterns = [
            r'[Python|Java|C\+\+|JavaScript|Go|Rust]',
            r'[MySQL|MongoDB|Redis|PostgreSQL]',
            r'[Docker|Kubernetes|Linux]',
            r'[AWS|阿里云|腾讯云]',
            r'[Spring|Django|Flask|React|Vue]',
            r'[机器学习 | 深度学习|AI|NLP|CV]',
            r'[数据分析 | 数据可视化|SQL]',
            r'[Git|SVN|CI/CD]'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            skills.extend(matches)
        
        # 去重
        return list(set(skills))
    
    def _calculate_keyword_coverage(self, job: JobPosition, 
                                    resume_keywords: List[str]) -> float:
        """计算关键词覆盖度"""
        if not resume_keywords:
            return 0
        
        text = job.description + job.requirements
        
        covered = 0
        for keyword in resume_keywords:
            if keyword in text:
                covered += 1
        
        coverage_ratio = covered / len(resume_keywords)
        return min(coverage_ratio * 100, 100)
    
    def _is_similar(self, s1: str, s2: str) -> bool:
        """判断两个字符串是否相似"""
        # 完全匹配
        if s1 == s2:
            return True
        
        # 包含关系
        if s1 in s2 or s2 in s1:
            return True
        
        # 简繁体/同义词处理（可扩展）
        synonyms = {
            'python': ['py', 'python3'],
            'java': ['jvm', 'jdk'],
            'javascript': ['js'],
            'vue': ['vue.js'],
            'react': ['react.js']
        }
        
        s1_lower = s1.lower()
        s2_lower = s2.lower()
        
        for key, values in synonyms.items():
            if s1_lower == key and s2_lower in values:
                return True
            if s2_lower == key and s1_lower in values:
                return True
        
        return False
    
    def _evaluate_jd_quality(self, job: JobPosition) -> float:
        """评估 JD 质量"""
        score = 50  # 基础分
        
        # JD 长度评价
        desc_length = len(job.description + job.requirements)
        if 200 <= desc_length <= 1000:
            score += 20
        elif desc_length > 1000:
            score += 10
        
        # 是否有明确技能要求
        if job.skills:
            score += 15
        
        # 是否有清晰职责描述
        if '负责' in job.description or '职责' in job.description:
            score += 15
        
        return min(score, 100)


class JobFilter:
    """岗位筛选器主类"""
    
    def __init__(self, config: Dict = None):
        """
        Args:
            config: 筛选配置
                - cities: 目标城市
                - min_salary: 最低薪资
                - max_salary: 最高薪资
                - job_types: 工作类型
                - education: 学历要求
                - experience: 经验要求
                - min_score: 最小匹配分数
        """
        self.config = config or {}
        self.rule_engine = RuleEngine(
            cities=self.config.get('cities'),
            min_salary=self.config.get('min_salary', 0),
            max_salary=self.config.get('max_salary', 50000),
            job_types=self.config.get('job_types'),
            education=self.config.get('education'),
            experience=self.config.get('experience')
        )
        self.semantic_matcher = SemanticMatcher()
        self.min_score = self.config.get('min_score', 60)
    
    def filter_and_rank(self, jobs: List[JobPosition], 
                       resume_skills: List[str] = None,
                       resume_keywords: List[str] = None) -> List[JobPosition]:
        """
        筛选并排序岗位
        
        Args:
            jobs: 待筛选岗位列表
            resume_skills: 简历技能列表
            resume_keywords: 简历关键词列表
        
        Returns:
            按匹配度排序的岗位列表
        """
        log.info(f"开始筛选 {len(jobs)} 个岗位...")
        
        # 1. 规则筛选
        filtered_jobs = self.rule_engine.filter(jobs)
        
        if not filtered_jobs:
            log.warning("规则筛选后无匹配岗位，放宽条件重试...")
            return self._relaxed_filter(jobs)
        
        # 2. 语义匹配
        if resume_skills or resume_keywords:
            for job in filtered_jobs:
                score = self.semantic_matcher.match(
                    job,
                    resume_skills or [],
                    resume_keywords or []
                )
                job.score = score
        else:
            # 没有简历信息，按其他因素评分
            for job in filtered_jobs:
                job.score = self._score_without_resume(job)
        
        # 3. 过滤低分岗位
        qualified_jobs = [job for job in filtered_jobs if job.score >= self.min_score]
        
        # 4. 排序
        sorted_jobs = sorted(qualified_jobs, key=lambda x: x.score, reverse=True)
        
        log.success(f"筛选完成，推荐 {len(sorted_jobs)} 个高匹配岗位")
        
        return sorted_jobs
    
    def _relaxed_filter(self, jobs: List[JobPosition]) -> List[JobPosition]:
        """放宽条件重新筛选"""
        # 暂时只保留城市和薪资条件
        relaxed_rule = RuleEngine(
            cities=self.config.get('cities'),
            min_salary=self.config.get('min_salary', 0),
            max_salary=self.config.get('max_salary', 50000)
        )
        
        return relaxed_rule.filter(jobs)
    
    def _score_without_resume(self, job: JobPosition) -> float:
        """没有简历信息时的评分策略"""
        score = 50
        
        # 薪资评分
        avg_salary = (job.salary_min + job.salary_max) / 2
        if avg_salary >= 20:
            score += 20
        elif avg_salary >= 15:
            score += 15
        elif avg_salary >= 10:
            score += 10
        
        # 公司知名度（简化版）
        company_keywords = ['腾讯', '阿里', '字节', '美团', '百度', '微软', '谷歌']
        for keyword in company_keywords:
            if keyword in job.company:
                score += 10
                break
        
        # 发布时间
        if job.publish_date:
            days_ago = (datetime.now() - job.publish_date).days
            if days_ago <= 3:
                score += 10
            elif days_ago <= 7:
                score += 5
        
        return min(score, 100)
    
    def get_recommendations(self, jobs: List[JobPosition], top_n: int = 10) -> List[JobPosition]:
        """
        获取 Top N 推荐岗位
        
        Args:
            jobs: 岗位列表
            top_n: 推荐数量
        
        Returns:
            Top N 岗位
        """
        sorted_jobs = sorted(jobs, key=lambda x: x.score, reverse=True)
        return sorted_jobs[:top_n]
    
    def generate_report(self, jobs: List[JobPosition]) -> Dict:
        """
        生成筛选报告
        
        Args:
            jobs: 岗位列表
        
        Returns:
            报告字典
        """
        if not jobs:
            return {'total': 0, 'recommendations': []}
        
        # 薪资分布
        salaries = [(job.salary_min + job.salary_max) / 2 for job in jobs]
        avg_salary = sum(salaries) / len(salaries)
        
        # 城市分布
        city_counts = {}
        for job in jobs:
            city = job.city
            city_counts[city] = city_counts.get(city, 0) + 1
        
        # 行业分布（简化）
        industry_counts = {}
        for job in jobs:
            industry = job.company.split()[0] if job.company else '未知'
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
        
        return {
            'total': len(jobs),
            'avg_salary': round(avg_salary, 2),
            'city_distribution': city_counts,
            'industry_distribution': dict(list(industry_counts.items())[:5]),
            'top_companies': list(set([job.company for job in jobs[:20]]))
        }
