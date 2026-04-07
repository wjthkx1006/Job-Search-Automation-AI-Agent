"""
QualityChecker - 质量保障系统
确保简历修改质量和投递准确性
"""
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from modules.models import Resume, JobPosition, JDAnalysis, QualityCheckResult
from utils.logger import log


class ResumeQualityChecker:
    """简历质量检查器"""
    
    def __init__(self):
        # 必填字段
        self.required_fields = ['name', 'phone', 'email']
        
        # 技能关键词库（用于检查简历完整性）
        self.skill_categories = {
            'programming': ['Python', 'Java', 'C++', 'JavaScript', 'Go', 'Rust'],
            'database': ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL'],
            'framework': ['Spring', 'Django', 'Flask', 'React', 'Vue'],
            'tools': ['Git', 'Docker', 'Linux', 'Kubernetes']
        }
    
    def check(self, resume: Resume) -> QualityCheckResult:
        """
        全面检查简历质量
        
        Args:
            resume: 待检查的简历
        
        Returns:
            检查结果
        """
        checks = {}
        scores = {}
        suggestions = []
        
        # 1. 必填字段检查
        result, score = self._check_required_fields(resume)
        checks['required_fields'] = result
        scores['required_fields'] = score
        if not result:
            suggestions.append("请补充缺失的必填信息（姓名、电话、邮箱）")
        
        # 2. 联系方式格式检查
        result, score = self._check_contact_format(resume)
        checks['contact_format'] = result
        scores['contact_format'] = score
        if not result:
            suggestions.append("请检查电话和邮箱格式是否正确")
        
        # 3. 教育背景检查
        result, score = self._check_education(resume)
        checks['education'] = result
        scores['education'] = score
        if not result:
            suggestions.append("建议补充教育背景信息")
        
        # 4. 工作经历检查
        result, score = self._check_work_experience(resume)
        checks['work_experience'] = result
        scores['work_experience'] = score
        if not result:
            suggestions.append("建议补充工作经历描述")
        
        # 5. 项目经历检查
        result, score = self._check_projects(resume)
        checks['projects'] = result
        scores['projects'] = score
        if not result:
            suggestions.append("建议补充项目经历")
        
        # 6. 技能清单检查
        result, score = self._check_skills(resume)
        checks['skills'] = result
        scores['skills'] = score
        if not result:
            suggestions.append("建议补充技能清单")
        
        # 7. 内容长度检查
        result, score = self._check_content_length(resume)
        checks['content_length'] = result
        scores['content_length'] = score
        
        # 8. 语法错误检查
        result, score = self._check_grammar(resume)
        checks['grammar'] = result
        scores['grammar'] = score
        if not result:
            suggestions.append("建议检查简历中的错别字和语法错误")
        
        # 计算总体评分
        overall_score = sum(scores.values()) / len(scores) if scores else 0
        
        # 判断是否通过
        passed = all(checks.values()) and overall_score >= 70
        
        return QualityCheckResult(
            passed=passed,
            checks=checks,
            scores=scores,
            suggestions=suggestions,
            overall_score=round(overall_score, 2)
        )
    
    def _check_required_fields(self, resume: Resume) -> Tuple[bool, float]:
        """检查必填字段"""
        missing = []
        
        if not resume.name or not resume.name.strip():
            missing.append('姓名')
        if not resume.phone or not resume.phone.strip():
            missing.append('电话')
        if not resume.email or not resume.email.strip():
            missing.append('邮箱')
        
        if missing:
            return False, 0.0
        return True, 100.0
    
    def _check_contact_format(self, resume: Resume) -> Tuple[bool, float]:
        """检查联系方式格式"""
        score = 100
        
        # 手机号格式检查（中国大陆）
        phone_pattern = r'^1[3-9]\d{9}$'
        if resume.phone and not re.match(phone_pattern, resume.phone):
            score -= 50
        
        # 邮箱格式检查
        email_pattern = r'^[\w.-]+@[\w.-]+\.\w+$'
        if resume.email and not re.match(email_pattern, resume.email):
            score -= 50
        
        return score >= 80, score
    
    def _check_education(self, resume: Resume) -> Tuple[bool, float]:
        """检查教育背景"""
        if not resume.education:
            return False, 0
        
        # 检查是否有完整的教育信息
        complete_count = 0
        for edu in resume.education:
            if edu.get('school') and edu.get('major') and edu.get('degree'):
                complete_count += 1
        
        ratio = complete_count / len(resume.education)
        score = ratio * 100
        
        return ratio >= 0.8, score
    
    def _check_work_experience(self, resume: Resume) -> Tuple[bool, float]:
        """检查工作经历"""
        if not resume.work_experience:
            return False, 0
        
        # 检查是否有详细描述
        detailed_count = 0
        for exp in resume.work_experience:
            desc = exp.get('description', '')
            if len(desc) > 20:  # 描述长度大于 20 字符
                detailed_count += 1
        
        ratio = detailed_count / len(resume.work_experience)
        score = ratio * 100
        
        return ratio >= 0.7, score
    
    def _check_projects(self, resume: Resume) -> Tuple[bool, float]:
        """检查项目经历"""
        if not resume.projects:
            return False, 0
        
        # 检查项目描述的完整性
        detailed_count = 0
        for proj in resume.projects:
            desc = proj.get('description', '')
            if len(desc) > 20:
                detailed_count += 1
        
        ratio = detailed_count / len(resume.projects)
        score = ratio * 100
        
        return ratio >= 0.7, score
    
    def _check_skills(self, resume: Resume) -> Tuple[bool, float]:
        """检查技能清单"""
        if not resume.skills:
            return False, 0
        
        # 检查技能数量和质量
        skill_count = len(resume.skills)
        
        if skill_count < 3:
            return False, min(skill_count * 30, 60)
        
        # 检查技能多样性
        categories_covered = 0
        for category, skills in self.skill_categories.items():
            if any(skill in resume.skills for skill in skills):
                categories_covered += 1
        
        diversity_score = (categories_covered / len(self.skill_categories)) * 50
        
        return True, min(skill_count * 10 + diversity_score, 100)
    
    def _check_content_length(self, resume: Resume) -> Tuple[bool, float]:
        """检查内容长度合理性"""
        text = resume.to_text()
        length = len(text)
        
        # 合理长度范围：500-3000 字符
        if 500 <= length <= 3000:
            return True, 100
        elif length < 500:
            return False, max(length / 5, 30)
        else:
            return False, max(100 - (length - 3000) / 50, 50)
    
    def _check_grammar(self, resume: Resume) -> Tuple[bool, float]:
        """检查语法和拼写"""
        # 简化版：检查常见错误模式
        issues = []
        
        text = resume.to_text().lower()
        
        # 检查重复词
        words = text.split()
        for i in range(len(words) - 1):
            if words[i] == words[i + 1]:
                issues.append(f"重复词：{words[i]}")
        
        # 检查标点符号问题
        if '..' in text:
            issues.append("发现连续句号")
        
        # 检查空格问题
        if '  ' in text:
            issues.append("发现多余空格")
        
        if not issues:
            return True, 100
        
        # 根据问题数量扣分
        penalty = min(len(issues) * 10, 40)
        return False, 100 - penalty


class JDMatchChecker:
    """JD 匹配度检查器"""
    
    def __init__(self):
        self.min_match_score = 60  # 最小匹配分数阈值
    
    def check(self, resume: Resume, job: JobPosition, 
              match_score: float) -> QualityCheckResult:
        """
        检查简历与 JD 的匹配度
        
        Args:
            resume: 简历
            job: 岗位
            match_score: 匹配度分数
        
        Returns:
            检查结果
        """
        checks = {}
        scores = {}
        suggestions = []
        
        # 1. 匹配度检查
        checks['match_score'] = match_score >= self.min_match_score
        scores['match_score'] = match_score
        
        if match_score < self.min_match_score:
            suggestions.append(f"匹配度较低 ({match_score:.1f}分)，建议优化简历")
        
        # 2. 技能覆盖检查
        skill_check, skill_score = self._check_skill_coverage(resume, job)
        checks['skill_coverage'] = skill_check
        scores['skill_coverage'] = skill_score
        
        if not skill_check:
            suggestions.append("建议补充 JD 中要求的技能")
        
        # 3. 经验匹配检查
        exp_check, exp_score = self._check_experience_match(resume, job)
        checks['experience_match'] = exp_check
        scores['experience_match'] = exp_score
        
        # 4. 学历匹配检查
        edu_check, edu_score = self._check_education_match(job)
        checks['education_match'] = edu_check
        scores['education_match'] = edu_score
        
        # 5. 薪资期望检查
        salary_check, salary_score = self._check_salary_expectation(resume, job)
        checks['salary_expectation'] = salary_check
        scores['salary_expectation'] = salary_score
        
        # 计算总体评分
        overall_score = sum(scores.values()) / len(scores) if scores else 0
        
        # 判断是否通过
        passed = all(checks.values()) and overall_score >= 70
        
        return QualityCheckResult(
            passed=passed,
            checks=checks,
            scores=scores,
            suggestions=suggestions,
            overall_score=round(overall_score, 2)
        )
    
    def _check_skill_coverage(self, resume: Resume, job: JobPosition) -> Tuple[bool, float]:
        """检查技能覆盖度"""
        if not job.skills:
            return True, 100
        
        matched = 0
        for skill in job.skills:
            if skill in resume.skills:
                matched += 1
        
        coverage = matched / len(job.skills)
        score = coverage * 100
        
        return coverage >= 0.5, score
    
    def _check_experience_match(self, resume: Resume, job: JobPosition) -> Tuple[bool, float]:
        """检查经验匹配度"""
        # 简化版：检查工作年限
        required_exp = job.experience
        
        if '不限' in required_exp or not required_exp:
            return True, 100
        
        # 解析要求的工作年限
        exp_years = self._parse_experience_years(required_exp)
        
        # 计算简历中的工作经验年限
        resume_years = self._calculate_resume_experience(resume)
        
        if resume_years >= exp_years:
            return True, 100
        else:
            ratio = resume_years / exp_years if exp_years > 0 else 0
            return ratio >= 0.7, ratio * 100
    
    def _parse_experience_years(self, exp_str: str) -> int:
        """解析经验要求为年数"""
        if not exp_str:
            return 0
        
        # 提取数字
        import re
        numbers = re.findall(r'\d+', exp_str)
        
        if numbers:
            return int(numbers[0])
        
        return 0
    
    def _calculate_resume_experience(self, resume: Resume) -> int:
        """计算简历中的工作经验年限"""
        if not resume.work_experience:
            return 0
        
        # 简化版：假设每段工作经历平均 2 年
        return len(resume.work_experience) * 2
    
    def _check_education_match(self, job: JobPosition) -> Tuple[bool, float]:
        """检查学历匹配度"""
        required_edu = job.education
        
        if '不限' in required_edu or not required_edu:
            return True, 100
        
        # 简化版：只要不是明确要求更高学历就通过
        return True, 80
    
    def _check_salary_expectation(self, resume: Resume, job: JobPosition) -> Tuple[bool, float]:
        """检查薪资期望合理性"""
        # 简化版：默认通过
        return True, 100


class SubmissionValidator:
    """投递验证器"""
    
    def __init__(self):
        self.max_daily_submissions = 50  # 每日最大投递数
    
    def validate(self, job: JobPosition, resume: Resume,
                 daily_count: int) -> QualityCheckResult:
        """
        验证投递请求
        
        Args:
            job: 目标岗位
            resume: 简历
            daily_count: 今日已投递数量
        
        Returns:
            验证结果
        """
        checks = {}
        scores = {}
        suggestions = []
        
        # 1. 岗位信息完整性检查
        result, score = self._check_job_completeness(job)
        checks['job_completeness'] = result
        scores['job_completeness'] = score
        
        if not result:
            suggestions.append("岗位信息不完整，跳过投递")
        
        # 2. 投递链接有效性检查
        result, score = self._check_apply_url(job)
        checks['apply_url'] = result
        scores['apply_url'] = score
        
        if not result:
            suggestions.append("缺少投递链接，无法自动投递")
        
        # 3. 每日投递限制检查
        result, score = self._check_daily_limit(daily_count)
        checks['daily_limit'] = result
        scores['daily_limit'] = score
        
        if not result:
            suggestions.append(f"已达到每日投递上限 ({self.max_daily_submissions})")
        
        # 4. 去重检查
        result, score = self._check_duplicate(job)
        checks['duplicate'] = result
        scores['duplicate'] = score
        
        if not result:
            suggestions.append("该岗位已投递过")
        
        # 计算总体评分
        overall_score = sum(scores.values()) / len(scores) if scores else 0
        
        # 判断是否通过
        passed = all(checks.values())
        
        return QualityCheckResult(
            passed=passed,
            checks=checks,
            scores=scores,
            suggestions=suggestions,
            overall_score=round(overall_score, 2)
        )
    
    def _check_job_completeness(self, job: JobPosition) -> Tuple[bool, float]:
        """检查岗位信息完整性"""
        required_fields = ['title', 'company', 'url']
        
        missing = [field for field in required_fields if not getattr(job, field, None)]
        
        if missing:
            return False, 0
        
        return True, 100
    
    def _check_apply_url(self, job: JobPosition) -> Tuple[bool, float]:
        """检查投递链接"""
        # 如果 apply_url 不存在，使用 url
        if job.apply_url or job.url:
            return True, 100
        return False, 0
    
    def _check_daily_limit(self, daily_count: int) -> Tuple[bool, float]:
        """检查每日投递限制"""
        if daily_count < self.max_daily_submissions:
            return True, 100
        return False, 0
    
    def _check_duplicate(self, job: JobPosition) -> Tuple[bool, float]:
        """检查重复投递"""
        # 这里应该检查本地数据库或缓存
        # 简化版：默认不重复
        return True, 100


class QualityAssuranceManager:
    """质量保证管理器"""
    
    def __init__(self):
        self.resume_checker = ResumeQualityChecker()
        self.jd_match_checker = JDMatchChecker()
        self.submission_validator = SubmissionValidator()
    
    def comprehensive_check(self, resume: Resume, job: JobPosition,
                           match_score: float, daily_count: int) -> QualityCheckResult:
        """
        综合质量检查
        
        Args:
            resume: 简历
            job: 岗位
            match_score: 匹配度分数
            daily_count: 今日已投递数
        
        Returns:
            综合检查结果
        """
        log.info("开始综合质量检查...")
        
        # 1. 简历质量检查
        resume_result = self.resume_checker.check(resume)
        
        # 2. JD 匹配度检查
        match_result = self.jd_match_checker.check(resume, job, match_score)
        
        # 3. 投递验证
        submit_result = self.submission_validator.validate(job, resume, daily_count)
        
        # 合并结果
        all_checks = {**resume_result.checks, **match_result.checks, **submit_result.checks}
        all_scores = {**resume_result.scores, **match_result.scores, **submit_result.scores}
        all_suggestions = list(set(resume_result.suggestions + match_result.suggestions + submit_result.suggestions))
        
        overall_score = sum(all_scores.values()) / len(all_scores) if all_scores else 0
        passed = resume_result.passed and match_result.passed and submit_result.passed
        
        log.success(f"质量检查完成：{'通过' if passed else '未通过'} (得分：{overall_score:.1f})")
        
        return QualityCheckResult(
            passed=passed,
            checks=all_checks,
            scores=all_scores,
            suggestions=all_suggestions,
            overall_score=round(overall_score, 2)
        )
    
    def get_recommendations(self, result: QualityCheckResult) -> List[str]:
        """
        获取改进建议
        
        Args:
            result: 检查结果
        
        Returns:
            建议列表
        """
        recommendations = []
        
        # 根据各项检查结果给出建议
        if not result.checks.get('required_fields'):
            recommendations.append("请完善简历基本信息（姓名、电话、邮箱）")
        
        if not result.checks.get('skills'):
            recommendations.append("建议补充更多技术技能描述")
        
        if not result.checks.get('match_score'):
            recommendations.append("匹配度较低，建议针对 JD 调整简历重点")
        
        if result.overall_score < 70:
            recommendations.append("简历整体质量有待提升，建议进行全面优化")
        
        if result.suggestions:
            recommendations.extend(result.suggestions)
        
        return recommendations
