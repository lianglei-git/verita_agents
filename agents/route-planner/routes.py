"""MVP 成长路线目录（demo）。"""

from __future__ import annotations

ROUTES: list[dict] = [
    {
        "id": "global-career-interview",
        "name": "海外面试线",
        "tagline": "前端工程师 → 海外面试 → 项目表达 → 远程协作",
        "description": "适合目标为海外技术岗位、需要面试与英语项目表达的学习者。",
        "stages": [
            {"id": "s1", "title": "自我介绍", "focus": "Who you are"},
            {"id": "s2", "title": "项目叙述", "focus": "What you built"},
            {"id": "s3", "title": "技术面试", "focus": "Deep dive Q&A"},
            {"id": "s4", "title": "远程协作", "focus": "Async communication"},
        ],
        "keywords": ["面试", "海外", "offer", "技术面试", "global", "interview"],
        "primary_track": "Global Career",
    },
    {
        "id": "remote-work",
        "name": "远程工作线",
        "tagline": "英语沟通 → 异步协作 → 跨时区会议",
        "description": "适合已有一定基础、希望提升远程团队沟通效率的学习者。",
        "stages": [
            {"id": "s1", "title": "工作区英语", "focus": "Slack & email"},
            {"id": "s2", "title": "站会表达", "focus": "Stand-up"},
            {"id": "s3", "title": "文档写作", "focus": "RFC & PRD"},
            {"id": "s4", "title": "冲突处理", "focus": "Negotiation"},
        ],
        "keywords": ["远程", "remote", "协作", "分布式"],
        "primary_track": "Remote Work",
    },
    {
        "id": "study-abroad",
        "name": "留学考试线",
        "tagline": "学术英语 → 考试技巧 → 申请沟通",
        "description": "适合雅思/托福备考与留学申请场景。",
        "stages": [
            {"id": "s1", "title": "学术阅读", "focus": "Academic reading"},
            {"id": "s2", "title": "听力技巧", "focus": "Exam listening"},
            {"id": "s3", "title": "写作模板", "focus": "Essay structure"},
            {"id": "s4", "title": "面试口语", "focus": "Admission talk"},
        ],
        "keywords": ["留学", "雅思", "托福", "ielts", "toefl", "考试"],
        "primary_track": "Study Abroad",
    },
]

DEFAULT_ROUTE_ID = "global-career-interview"
