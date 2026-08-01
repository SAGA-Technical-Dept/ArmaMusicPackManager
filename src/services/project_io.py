"""项目持久化：JSON 序列化/反序列化 (.amp.json)。"""

from __future__ import annotations

import json
import os

from ..models import Project

PROJECT_EXT = ".amp.json"


def save_project(project: Project, path: str) -> None:
    """保存项目到 JSON 文件。"""
    project.project_file = path
    payload = {"format": "arma-music-pack", "version": 1, **project.to_dict()}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_project(path: str) -> Project:
    """从 JSON 文件加载项目。"""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    project = Project.from_dict(payload)
    project.project_file = path
    return project
