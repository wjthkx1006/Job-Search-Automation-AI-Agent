"""
ResumeAdapter - 简历定制模块
基于 Qwen LLM 实现 JD 驱动的简历优化和定制
"""
import re
import os
import json
import requests
from typing import List, Dict, Optional, Tuple
from modules.models import Resume, JobPosition, JDAnalysis
from utils.logger import log


class QwenLLMClient:
    """Qwen LLM 客户端"""
    
    def __init__(self, api_key: str, model: str = "qwen-turbo"):
        self.api_key = api_key
        self.model = model
        self.url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    def generate(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """
        调用 Qwen 模型生成内容
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成长度
        
        Returns:
            生成的文本
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的求职助手，擅长优化简历和匹配岗位。请提供简洁、实用的建议。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                },
                "parameters": {
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                }
            }
            
            response = requests.post(self.url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("output") and result["output"].get("text"):
                return result["output"]["text"]
            else:
                log.warning(f"Qwen API 返回异常：{result}")
                return None
                
        except Exception as e:
            log.error(f"Qwen API 调用失败：{str(e)}")
            return None


class JDParser:
    """JD 解析器 - 提取关键信息"""
    
    def __init__(self):
        # 常见技能关键词库
        self.skill_keywords = {
            'programming': ['Python', 'Java', 'C++', 'JavaScript', 'Go', 'Rust', 'PHP', 'Ruby'],
            'database': ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server'],
            'framework': ['Spring', 'Django', 'Flask', 'FastAPI', 'React', 'Vue', 'Angular'],
            'cloud': ['AWS', '阿里云', '腾讯云', 'Azure', 'Google Cloud'],
            'devops': ['Docker', 'Kubernetes', 'Linux', 'CI/CD', 'Jenkins', 'GitLab'],
            'ai_ml': ['机器学习', '深度学习', 'NLP', 'CV', 'PyTorch', 'TensorFlow', 'Scikit-learn']
        }
    
    def parse(self, job: JobPosition) -> JDAnalysis:
        """
        解析 JD
        
        Args:
            job: 岗位信息
        
        Returns:
            JD 分析结果
        """
        text = job.description + job.requirements
        
        analysis = JDAnalysis(
            key_skills=self._extract_skills(text),
            required_qualifications=self._extract_requirements(text),
            preferred_qualifications=self._extract_preferred(text),
            responsibilities=self._extract_responsibilities(text),
            salary_range=self._parse_salary_range(job.salary_min, job.salary_max),
            location=job.city,
            company_type=self._infer_company_type(job.company),
            industry=self._infer_industry(text),
            keywords_density=self._calculate_keyword_density(text)
        )
        
        log.debug(f"JD 解析完成：{job.title}")
        return analysis
    
    def _extract_skills(self, text: str) -> List[str]:
        """提取技能要求"""
        skills = []
        
        for category, keywords in self.skill_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    skills.append(keyword)
        
        # 额外提取其他常见技能
        extra_patterns = [
            r'[办公软件 |Office|WPS]',
            r'[英语 |CET-4|CET-6|TOEFL|IELTS]',
            r'[沟通能力 |团队协作 |领导力]',
            r'[数据分析 |可视化]'
        ]
        
        for pattern in extra_patterns:
            matches = re.findall(pattern, text)
            skills.extend(matches)
        
        return list(set(skills))
    
    def _extract_requirements(self, text: str) -> List[str]:
        """提取必备要求"""
        requirements = []
        
        # 匹配"要求"、"必须"、"需要"等关键词后的内容
        patterns = [
            r'(?:要求 |必须 |需要)[：:]?\s*([^。；\n]+)',
            r'(?:具备 |拥有)[：:]?\s*([^。；\n]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            requirements.extend(matches)
        
        # 过滤出简短的要求项
        filtered = []
        for req in requirements:
            req = req.strip()
            if 5 <= len(req) <= 50:  # 长度限制
                filtered.append(req)
        
        return filtered[:10]  # 最多 10 条
    
    def _extract_preferred(self, text: str) -> List[str]:
        """提取优先要求"""
        preferred = []
        
        patterns = [
            r'(?:优先 |加分项)[：:]?\s*([^。；\n]+)',
            r'(?:熟悉 |了解)[：:]?\s*([^。；\n]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            preferred.extend(matches)
        
        return [p.strip() for p in preferred if 5 <= len(p.strip()) <= 50]
    
    def _extract_responsibilities(self, text: str) -> List[str]:
        """提取职责描述"""
        responsibilities = []
        
        # 匹配"负责"、"职责"等关键词
        pattern = r'(?:负责 |职责)[：:]?\s*([^。；\n]+(?:[^。；\n]+)?)'
        matches = re.findall(pattern, text)
        
        for match in matches:
            resp = match.strip()
            if 10 <= len(resp) <= 200:
                responsibilities.append(resp)
        
        return responsibilities[:5]
    
    def _parse_salary_range(self, min_sal: int, max_sal: int) -> Optional[Tuple[int, int]]:
        """解析薪资范围"""
        if min_sal > 0 and max_sal > 0:
            return (min_sal, max_sal)
        return None
    
    def _infer_company_type(self, company_name: str) -> str:
        """推断公司类型"""
        if not company_name:
            return "未知"
        
        keywords = {
            '互联网': ['腾讯', '阿里', '字节', '美团', '百度', '京东', '网易'],
            '外企': ['微软', '谷歌', '亚马逊', 'facebook', 'apple', 'ibm'],
            '金融': ['银行', '证券', '基金', '保险', '支付'],
            '游戏': ['游戏', '电竞', '互动娱乐'],
            '电商': ['电商', '购物', '零售']
        }
        
        for ctype, keywords_list in keywords.items():
            for keyword in keywords_list:
                if keyword in company_name:
                    return ctype
        
        return "其他"
    
    def _infer_industry(self, text: str) -> str:
        """推断行业领域"""
        industry_keywords = {
            '人工智能': ['AI', '人工智能', '机器学习', '深度学习', 'NLP', 'CV'],
            '金融科技': ['金融', '支付', '区块链', '数字货币'],
            '电子商务': ['电商', '购物', '零售', '供应链'],
            '企业服务': ['SaaS', 'B 端', '企业级', 'CRM', 'ERP']
        }
        
        for industry, keywords in industry_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return industry
        
        return "互联网"
    
    def _calculate_keyword_density(self, text: str) -> Dict[str, float]:
        """计算关键词密度"""
        density = {}
        words = re.findall(r'\w+', text)
        total_words = len(words)
        
        if total_words == 0:
            return density
        
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        for word, count in word_counts.items():
            if len(word) >= 2:  # 忽略短词
                density[word] = round(count / total_words * 100, 2)
        
        # 取前 20 个高频词
        sorted_density = dict(sorted(density.items(), key=lambda x: x[1], reverse=True)[:20])
        
        return sorted_density


class ResumeOptimizer:
    """简历优化器 - 基于 Qwen LLM 定制简历"""
    
    def __init__(self, api_key: str = None, model: str = "qwen-turbo"):
        """
        Args:
            api_key: Qwen API Key
            model: 使用的模型
        """
        # 从环境变量或参数获取 API Key
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model
        
        # 初始化 LLM 客户端
        if self.api_key:
            self.llm_client = QwenLLMClient(api_key=self.api_key, model=model)
            log.success("Qwen LLM 客户端已初始化")
        else:
            self.llm_client = None
            log.warning("未配置 LLM API Key，将使用基础版简历定制")
        
        self.jd_parser = JDParser()
        
        # 简历模板
        self.templates = {
            'standard': self._get_standard_template,
            'project_focused': self._get_project_focused_template,
            'experience_focused': self._get_experience_focused_template
        }
    
    def adapt(self, resume: Resume, job: JobPosition, 
              optimize: bool = True) -> Resume:
        """
        根据 JD 定制简历
        
        Args:
            resume: 原始简历
            job: 目标岗位
            optimize: 是否进行 AI 优化
        
        Returns:
            定制后的简历
        """
        log.info(f"开始为 {job.title} @ {job.company} 定制简历...")
        
        # 1. 解析 JD
        jd_analysis = self.jd_parser.parse(job)
        
        # 2. 提取关键技能
        required_skills = jd_analysis.key_skills
        
        # 3. 定制简历
        adapted_resume = self._create_adapted_resume(resume, job, jd_analysis)
        
        # 4. AI 优化（如果启用且有 LLM 客户端）
        if optimize and self.llm_client:
            try:
                optimized_resume = self._llm_optimize(adapted_resume, job, jd_analysis)
                if optimized_resume:
                    adapted_resume = optimized_resume
                    log.success("AI 优化完成")
            except Exception as e:
                log.warning(f"LLM 优化失败，使用基础版本：{str(e)}")
        elif not self.llm_client:
            log.info("跳过 AI 优化（未配置 API Key）")
        
        log.success(f"简历定制完成：{job.title}")
        return adapted_resume
    
    def _create_adapted_resume(self, resume: Resume, job: JobPosition,
                               jd_analysis: JDAnalysis) -> Resume:
        """创建定制版简历"""
        
        # 调整自我评价以匹配 JD
        customized_self_eval = self._customize_self_evaluation(
            resume.self_evaluation,
            job,
            jd_analysis
        )
        
        # 调整技能顺序，将 JD 要求的技能前置
        reordered_skills = self._reorder_skills(
            resume.skills,
            jd_analysis.key_skills
        )
        
        # 返回新简历对象
        return Resume(
            name=resume.name,
            phone=resume.phone,
            email=resume.email,
            education=resume.education,
            work_experience=resume.work_experience,
            projects=resume.projects,
            skills=reordered_skills,
            certificates=resume.certificates,
            self_evaluation=customized_self_eval
        )
    
    def _customize_self_evaluation(self, original: str, job: JobPosition,
                                   jd_analysis: JDAnalysis) -> str:
        """定制自我评价"""
        if not original:
            # 如果没有自我评价，生成一个基于 JD 的
            skills_str = ', '.join(jd_analysis.key_skills[:5])
            return f"对{skills_str}有深入理解，具备丰富的实战经验。热衷于技术钻研，能够快速适应新技术。期望在{job.title}岗位上发挥所长。"
        
        # 在原有基础上添加 JD 相关关键词
        intro_parts = original.split('\n')
        
        # 在第一段插入技能关键词
        if intro_parts:
            skills_mention = f"熟练掌握{', '.join(jd_analysis.key_skills[:3])}"
            if not any(skill in intro_parts[0] for skill in jd_analysis.key_skills):
                intro_parts[0] = skills_mention + "。" + intro_parts[0]
        
        return '\n'.join(intro_parts)
    
    def _reorder_skills(self, skills: List[str], priority_skills: List[str]) -> List[str]:
        """重新排序技能，将优先级高的技能前置"""
        if not priority_skills:
            return skills
        
        reordered = []
        added = set()
        
        # 先添加优先级技能
        for skill in priority_skills:
            if skill in skills and skill not in added:
                reordered.append(skill)
                added.add(skill)
        
        # 再添加剩余技能
        for skill in skills:
            if skill not in added:
                reordered.append(skill)
        
        return reordered[:15]  # 限制技能数量
    
    def _llm_optimize(self, resume: Resume, job: JobPosition,
                      jd_analysis: JDAnalysis) -> Optional[Resume]:
        """使用 Qwen LLM 优化简历"""
        try:
            # 构建提示词
            prompt = self._build_optimize_prompt(resume, job, jd_analysis)
            
            log.info("正在调用 Qwen LLM 优化简历...")
            
            # 调用 LLM
            optimized_text = self.llm_client.generate(prompt, max_tokens=3000)
            
            if not optimized_text:
                return None
            
            # 解析优化结果
            optimized_resume = self._parse_optimized_resume(optimized_text, resume, job)
            
            return optimized_resume
            
        except Exception as e:
            log.error(f"LLM 优化异常：{str(e)}")
            return None
    
    def _build_optimize_prompt(self, resume: Resume, job: JobPosition,
                               jd_analysis: JDAnalysis) -> str:
        """构建优化提示词"""
        
        # 格式化简历信息
        resume_info = f"""
【原始简历】
姓名：{resume.name}
电话：{resume.phone}
邮箱：{resume.email}

教育背景：
{' | '.join([f"{e.get('school', '')}{e.get('major', '')}{e.get('degree', '')}" for e in resume.education])}

工作经历：
{chr(10).join([f"- {w.get('company', '')}{w.get('position', '')}{w.get('time', '')}\n  {w.get('description', '')}" for w in resume.work_experience])}

项目经历：
{chr(10).join([f"- {p.get('name', '')}\n  {p.get('description', '')}" for p in resume.projects])}

技能清单：
{', '.join(resume.skills)}

证书资质：
{', '.join(resume.certificates)}

自我评价：
{resume.self_evaluation}
"""
        
        # 格式化 JD 信息
        jd_info = f"""
【目标岗位】
岗位：{job.title}
公司：{job.company}
城市：{job.city}
薪资：{job.get_salary_range()}

关键技能要求：
{', '.join(jd_analysis.key_skills)}

主要职责：
{chr(10).join([f"- {r}" for r in jd_analysis.responsibilities[:3]])}

其他要求：
{', '.join(jd_analysis.required_qualifications[:5])}
"""
        
        # 优化指令
        optimize_instruction = """
请根据目标岗位的 JD，对简历进行优化。要求：
1. 调整自我评价，突出与岗位匹配的技能和经验
2. 优化工作经历和项目描述，强调与 JD 相关的成果
3. 调整技能顺序，将 JD 要求的技能放在前面
4. 保持真实，不要虚构经历
5. 输出格式为 JSON，包含以下字段：
   - self_evaluation: 优化后的自我评价
   - work_experience: 优化后的工作经历（数组）
   - projects: 优化后的项目经历（数组）
   - skills: 优化后的技能列表（数组）

请直接输出 JSON 格式，不要有其他内容。
"""
        
        return resume_info + "\n\n" + jd_info + "\n\n" + optimize_instruction
    
    def _parse_optimized_resume(self, optimized_text: str, 
                                original: Resume,
                                job: JobPosition) -> Resume:
        """解析 LLM 返回的优化结果"""
        try:
            # 尝试解析 JSON
            import json
            # 清理可能的 markdown 标记
            optimized_text = optimized_text.strip()
            if optimized_text.startswith("```json"):
                optimized_text = optimized_text[7:]
            if optimized_text.endswith("```"):
                optimized_text = optimized_text[:-3]
            optimized_text = optimized_text.strip()
            
            data = json.loads(optimized_text)
            
            # 构建优化后的简历
            return Resume(
                name=original.name,
                phone=original.phone,
                email=original.email,
                education=original.education,
                work_experience=data.get('work_experience', original.work_experience),
                projects=data.get('projects', original.projects),
                skills=data.get('skills', original.skills),
                certificates=original.certificates,
                self_evaluation=data.get('self_evaluation', original.self_evaluation)
            )
            
        except Exception as e:
            log.warning(f"解析 LLM 返回结果失败：{str(e)}")
            log.debug(f"返回内容：{optimized_text}")
            
            # 如果解析失败，使用基础定制版本
            return original
    
    def _get_standard_template(self) -> str:
        """标准简历模板"""
        return """
姓名：{name}
电话：{phone}
邮箱：{email}

教育背景：
{education}

工作经历：
{work_experience}

项目经历：
{projects}

技能清单：
{skills}

证书资质：
{certificates}

自我评价：
{self_evaluation}
"""
    
    def _get_project_focused_template(self) -> str:
        """项目导向模板"""
        return """
姓名：{name}
电话：{phone}
邮箱：{email}

核心技能：
{skills}

项目经历：
{projects}

工作经历：
{work_experience}

教育背景：
{education}

证书资质：
{certificates}

自我评价：
{self_evaluation}
"""
    
    def _get_experience_focused_template(self) -> str:
        """经验导向模板"""
        return """
姓名：{name}
电话：{phone}
邮箱：{email}

工作经历：
{work_experience}

项目经历：
{projects}

核心技能：
{skills}

教育背景：
{education}

证书资质：
{certificates}

自我评价：
{self_evaluation}
"""


class ResumeGenerator:
    """简历生成器 - 导出多种格式"""
    
    @staticmethod
    def to_text(resume: Resume) -> str:
        """转换为纯文本"""
        content = f"{resume.name}\n{resume.phone}\n{resume.email}\n\n"
        
        # 教育背景
        if resume.education:
            content += "## 教育背景\n"
            for edu in resume.education:
                content += f"- {edu.get('school', '')} | {edu.get('major', '')} | {edu.get('degree', '')}\n"
            content += "\n"
        
        # 工作经历
        if resume.work_experience:
            content += "## 工作经历\n"
            for exp in resume.work_experience:
                content += f"- {exp.get('company', '')} | {exp.get('position', '')} | {exp.get('time', '')}\n"
                if exp.get('description'):
                    content += f"  {exp['description']}\n"
            content += "\n"
        
        # 项目经历
        if resume.projects:
            content += "## 项目经历\n"
            for proj in resume.projects:
                content += f"- {proj.get('name', '')}\n"
                if proj.get('description'):
                    content += f"  {proj['description']}\n"
            content += "\n"
        
        # 技能清单
        if resume.skills:
            content += f"## 技能清单\n{' '.join(resume.skills)}\n\n"
        
        # 自我评价
        if resume.self_evaluation:
            content += f"## 自我评价\n{resume.self_evaluation}\n"
        
        return content
    
    @staticmethod
    def to_markdown(resume: Resume) -> str:
        """转换为 Markdown 格式"""
        return ResumeGenerator.to_text(resume)
    
    @staticmethod
    def to_html(resume: Resume) -> str:
        """转换为 HTML 格式"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} 的简历</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
        h1 {{ color: #333; border-bottom: 2px solid #333; }}
        h2 {{ color: #666; border-left: 4px solid #666; padding-left: 10px; }}
        .contact {{ color: #666; }}
        .section {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>{name}</h1>
    <p class="contact">{phone} | {email}</p>
    
    {'<div class="section"><h2>教育背景</h2>' + ''.join([f'<p>- {e.get("school", "")} | {e.get("major", "")} | {e.get("degree", "")}</p>' for e in resume.education]) + '</div>' if resume.education else ''}
    
    {'<div class="section"><h2>工作经历</h2>' + ''.join([f'<p>- {e.get("company", "")} | {e.get("position", "")} | {e.get("time", "")}<br>{e.get("description", "")}</p>' for e in resume.work_experience]) + '</div>' if resume.work_experience else ''}
    
    {'<div class="section"><h2>项目经历</h2>' + ''.join([f'<p>- {p.get("name", "")}<br>{p.get("description", "")}</p>' for p in resume.projects]) + '</div>' if resume.projects else ''}
    
    {'<div class="section"><h2>技能清单</h2><p>' + ' | '.join(resume.skills) + '</p></div>' if resume.skills else ''}
    
    {'<div class="section"><h2>自我评价</h2><p>' + resume.self_evaluation + '</p></div>' if resume.self_evaluation else ''}
</body>
</html>
""".format(
            name=resume.name,
            phone=resume.phone,
            email=resume.email,
            resume=resume
        )
        
        return html
