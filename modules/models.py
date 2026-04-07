"""
数据模型定义
使用 Pydantic 进行数据验证和序列化
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class JobPosition(BaseModel):
    """岗位信息模型"""
    
    id: str = Field(..., description="岗位唯一 ID")
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    city: str = Field(..., description="工作城市")
    salary_min: int = Field(default=0, description="最低薪资（元/月）")
    salary_max: int = Field(default=0, description="最高薪资（元/月）")
    job_type: str = Field(default="全职", description="工作类型")
    education: str = Field(default="不限", description="学历要求")
    experience: str = Field(default="不限", description="经验要求")
    publish_date: Optional[datetime] = Field(default=None, description="发布日期")
    update_date: Optional[datetime] = Field(default=None, description="更新日期")
    description: str = Field(default="", description="岗位职责")
    requirements: str = Field(default="", description="任职要求")
    skills: List[str] = Field(default_factory=list, description="技能要求")
    platform: str = Field(..., description="信息来源平台")
    url: str = Field(..., description="岗位链接")
    is_intern: bool = Field(default=False, description="是否为实习岗位")
    applied: bool = Field(default=False, description="是否已投递")
    apply_url: Optional[str] = Field(default=None, description="投递链接")
    score: float = Field(default=0.0, description="匹配度评分")
    
    @validator('salary_min', 'salary_max')
    def validate_salary(cls, v):
        if v < 0:
            raise ValueError('薪资不能为负数')
        return v
    
    def get_salary_range(self) -> str:
        """获取薪资范围字符串"""
        if self.salary_min == 0 and self.salary_max == 0:
            return "面议"
        elif self.salary_max == 0:
            return f"{self.salary_min}K+"
        elif self.salary_min == self.salary_max:
            return f"{self.salary_min}K"
        else:
            return f"{self.salary_min}-{self.salary_max}K"
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Resume(BaseModel):
    """简历模型"""
    
    name: str = Field(..., description="姓名")
    phone: str = Field(..., description="手机号")
    email: str = Field(..., description="邮箱")
    education: List[Dict[str, str]] = Field(default_factory=list, description="教育背景")
    work_experience: List[Dict[str, Any]] = Field(default_factory=list, description="工作经历")
    projects: List[Dict[str, Any]] = Field(default_factory=list, description="项目经历")
    skills: List[str] = Field(default_factory=list, description="技能清单")
    certificates: List[str] = Field(default_factory=list, description="证书资质")
    self_evaluation: str = Field(default="", description="自我评价")
    
    def to_text(self) -> str:
        """转换为纯文本格式"""
        content = f"{self.name}\n{self.phone}\n{self.email}\n\n"
        
        # 教育背景
        if self.education:
            content += "## 教育背景\n"
            for edu in self.education:
                content += f"- {edu.get('school', '')} | {edu.get('major', '')} | {edu.get('degree', '')}\n"
            content += "\n"
        
        # 工作经历
        if self.work_experience:
            content += "## 工作经历\n"
            for exp in self.work_experience:
                content += f"- {exp.get('company', '')} | {exp.get('position', '')} | {exp.get('time', '')}\n"
                if exp.get('description'):
                    content += f"  {exp['description']}\n"
            content += "\n"
        
        # 项目经历
        if self.projects:
            content += "## 项目经历\n"
            for proj in self.projects:
                content += f"- {proj.get('name', '')}\n"
                if proj.get('description'):
                    content += f"  {proj['description']}\n"
            content += "\n"
        
        # 技能清单
        if self.skills:
            content += f"## 技能清单\n{' '.join(self.skills)}\n\n"
        
        # 自我评价
        if self.self_evaluation:
            content += f"## 自我评价\n{self.self_evaluation}\n"
        
        return content
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump()


class JDAnalysis(BaseModel):
    """JD 分析结果模型"""
    
    key_skills: List[str] = Field(default_factory=list, description="关键技能")
    required_qualifications: List[str] = Field(default_factory=list, description="必备 qualifications")
    preferred_qualifications: List[str] = Field(default_factory=list, description="优先 qualifications")
    responsibilities: List[str] = Field(default_factory=list, description="主要职责")
    salary_range: Optional[tuple] = Field(default=None, description="薪资范围")
    location: str = Field(default="", description="工作地点")
    company_type: str = Field(default="", description="公司类型")
    industry: str = Field(default="", description="行业领域")
    keywords_density: Dict[str, float] = Field(default_factory=dict, description="关键词密度")


class ApplicationRecord(BaseModel):
    """投递记录模型"""
    
    job_id: str = Field(..., description="岗位 ID")
    job_title: str = Field(..., description="岗位标题")
    company: str = Field(..., description="公司名称")
    resume_version: str = Field(..., description="使用的简历版本")
    submit_time: datetime = Field(default_factory=datetime.now, description="提交时间")
    status: str = Field(default="submitted", description="状态：submitted/success/failed")
    message: str = Field(default="", description="反馈消息")
    screenshot_path: Optional[str] = Field(default=None, description="截图路径")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QualityCheckResult(BaseModel):
    """质量检查结果模型"""
    
    passed: bool = Field(default=False, description="是否通过检查")
    checks: Dict[str, bool] = Field(default_factory=dict, description="各项检查结果")
    scores: Dict[str, float] = Field(default_factory=dict, description="各项得分")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    overall_score: float = Field(default=0.0, description="总体评分")
