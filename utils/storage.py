"""
数据持久化模块
使用 JSON 文件存储采集岗位和投递记录
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from modules.models import JobPosition, ApplicationRecord
from utils.logger import log


class JsonStorage:
    """JSON 文件存储管理器"""

    def __init__(self, data_dir: Path = None):
        from config.config import settings
        self.data_dir = data_dir or settings.DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_dir / "jobs.json"
        self.records_file = self.data_dir / "application_records.json"

    def save_jobs(self, jobs: List[JobPosition]) -> int:
        """保存岗位列表，增量合并并去重"""
        existing = self.load_jobs()
        existing_map = {j.id: j for j in existing}

        new_count = 0
        for job in jobs:
            if job.id not in existing_map:
                existing_map[job.id] = job
                new_count += 1

        all_jobs = list(existing_map.values())
        data = [self._job_to_dict(j) for j in all_jobs]

        self._write_json(self.jobs_file, data)
        log.info(f"持久化存储：新增 {new_count} 个岗位，总计 {len(all_jobs)} 个")
        return new_count

    def load_jobs(self) -> List[JobPosition]:
        """加载已存储的岗位"""
        raw = self._read_json(self.jobs_file)
        if not raw:
            return []
        jobs = []
        for item in raw:
            try:
                jobs.append(self._dict_to_job(item))
            except Exception as e:
                log.debug(f"加载岗位记录失败：{str(e)}")
        return jobs

    def save_records(self, records: List[ApplicationRecord]) -> int:
        """保存投递记录"""
        existing = self.load_records()
        existing_ids = {(r.job_id, r.submit_time.isoformat() if isinstance(r.submit_time, datetime) else str(r.submit_time)) for r in existing}

        new_count = 0
        for rec in records:
            key = (rec.job_id, rec.submit_time.isoformat() if isinstance(rec.submit_time, datetime) else str(rec.submit_time))
            if key not in existing_ids:
                existing.append(rec)
                new_count += 1

        data = [r.model_dump(mode='json') for r in existing]
        self._write_json(self.records_file, data)
        log.info(f"持久化存储：新增 {new_count} 条投递记录")
        return new_count

    def load_records(self) -> List[ApplicationRecord]:
        """加载投递记录"""
        raw = self._read_json(self.records_file)
        if not raw:
            return []
        records = []
        for item in raw:
            try:
                if isinstance(item.get('submit_time'), str):
                    item['submit_time'] = datetime.fromisoformat(item['submit_time'])
                records.append(ApplicationRecord(**item))
            except Exception as e:
                log.debug(f"加载投递记录失败：{str(e)}")
        return records

    def get_submitted_job_ids(self) -> set:
        """获取已投递的岗位 ID 集合"""
        records = self.load_records()
        return {r.job_id for r in records}

    def _write_json(self, path: Path, data):
        tmp_path = path.with_suffix('.tmp')
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp_path.replace(path)
        except Exception as e:
            log.error(f"写入 JSON 文件失败 {path}: {str(e)}")
            if tmp_path.exists():
                tmp_path.unlink()

    def _read_json(self, path: Path) -> Optional[list]:
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"读取 JSON 文件失败 {path}: {str(e)}")
            return None

    @staticmethod
    def _job_to_dict(job: JobPosition) -> dict:
        data = job.model_dump(mode='json')
        if data.get('publish_date') and isinstance(data['publish_date'], str):
            pass
        return data

    @staticmethod
    def _dict_to_job(data: dict) -> JobPosition:
        for key in ('publish_date', 'update_date'):
            val = data.get(key)
            if isinstance(val, str):
                try:
                    data[key] = datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    data[key] = None
        return JobPosition(**data)
