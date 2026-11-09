"""Built-in Space Fractions sample used by Mock mode.

The sample lives as a real, separately testable project under
``space_code_agent/samples/space_fractions``.  Mock mode replays it through the
same write_file tool calls that the real model would issue, so the orchestrator,
path policy, validator and report pipeline are all exercised for real.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..agent.planner import Deviation, PlanFile, PlanTask, ProjectPlan
from ..core.requirements import NormalizedRequirements
from ..providers.mock import ProviderResponse, tool_response

SAMPLE_DIR_NAME = "space_fractions"

REQUIREMENT_MAP: dict[str, list[str]] = {
    "README.md": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-2", "FR-DERIVED-3", "NFR-1", "ASR-1", "ASR-2"],
    "docs/architecture-summary.md": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-2", "FR-DERIVED-3",
                                     "NFR-1", "ASR-1", "ASR-2"],
    "docs/ASSUMPTIONS.md": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-2", "FR-DERIVED-3",
                            "NFR-1", "ASR-1", "ASR-2"],
    "lib/http.js": ["FR-1", "NFR-1"],
    "services/question-service/src/questions.js": ["FR-DERIVED-2"],
    "services/question-service/src/store.js": ["FR-DERIVED-2", "ASR-1"],
    "services/question-service/src/index.js": ["FR-DERIVED-2", "ASR-2"],
    "services/question-service/src/server.js": ["FR-DERIVED-2"],
    "services/question-service/tests/questions.test.js": ["FR-DERIVED-2", "ASR-2"],
    "services/game-service/src/game.js": ["FR-1", "FR-DERIVED-1"],
    "services/game-service/src/index.js": ["FR-1", "FR-DERIVED-1", "ASR-2"],
    "services/game-service/src/questionClient.js": ["FR-1", "NFR-1"],
    "services/game-service/src/server.js": ["FR-1"],
    "services/game-service/tests/game.test.js": ["FR-1", "FR-DERIVED-1"],
    "services/user-service/src/auth.js": ["ASR-2"],
    "services/user-service/src/index.js": ["ASR-2"],
    "services/user-service/src/server.js": ["ASR-2"],
    "services/user-service/tests/auth.test.js": ["ASR-2"],
    "apps/web/index.html": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-3"],
    "apps/web/src/main.js": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-3"],
    "apps/web/src/api.js": ["FR-1", "FR-DERIVED-1"],
    "apps/web/src/styles.css": ["FR-1", "FR-DERIVED-3"],
    "apps/web/admin.html": ["FR-DERIVED-2"],
    "apps/web/src/admin.js": ["FR-DERIVED-2", "ASR-2"],
    "apps/web/server.js": ["FR-1", "NFR-1"],
    "tests/unit/http.test.js": ["FR-1", "NFR-1"],
    "tests/unit/schema.test.js": ["ASR-1"],
    "tests/e2e/flow.test.js": ["FR-1", "FR-DERIVED-1", "FR-DERIVED-2", "ASR-2"],
    "sql/init.sql": ["ASR-1"],
    "docker-compose.yml": ["NFR-1", "ASR-1"],
    "package.json": [],
    ".gitignore": [],
    ".env.example": [],
}

PURPOSES: dict[str, str] = {
    "README.md": "项目说明、运行方式、API 与假设",
    "package.json": "依赖声明与测试脚本",
    ".gitignore": "忽略依赖与本地密钥",
    ".env.example": "环境变量样例（仅占位符）",
    "docs/architecture-summary.md": "架构摘要与组件边界",
    "docs/ASSUMPTIONS.md": "假设、冲突与重大偏离",
    "lib/http.js": "零依赖 HTTP 路由与 JSON 工具",
    "services/question-service/src/questions.js": "题库种子数据",
    "services/question-service/src/store.js": "题目仓库与校验",
    "services/question-service/src/index.js": "题库 REST 接口",
    "services/question-service/src/server.js": "题库服务入口",
    "services/question-service/tests/questions.test.js": "题库接口测试",
    "services/game-service/src/game.js": "回合、判分领域逻辑",
    "services/game-service/src/index.js": "游戏 REST 接口",
    "services/game-service/src/questionClient.js": "题库服务客户端",
    "services/game-service/src/server.js": "游戏服务入口",
    "services/game-service/tests/game.test.js": "游戏领域与 API 测试",
    "services/user-service/src/auth.js": "HMAC 令牌与访客会话",
    "services/user-service/src/index.js": "用户 REST 接口",
    "services/user-service/src/server.js": "用户服务入口",
    "services/user-service/tests/auth.test.js": "认证测试",
    "apps/web/index.html": "学生端页面结构",
    "apps/web/src/main.js": "学生端状态机与交互",
    "apps/web/src/api.js": "游戏服务客户端",
    "apps/web/src/styles.css": "响应式太空主题样式",
    "apps/web/admin.html": "教师后台页面",
    "apps/web/src/admin.js": "题目增删改管理",
    "apps/web/server.js": "静态站点服务器",
    "tests/unit/http.test.js": "HTTP 工具单元测试",
    "tests/unit/schema.test.js": "持久化 DDL 结构与约束测试",
    "tests/e2e/flow.test.js": "跨服务端到端流程测试",
    "sql/init.sql": "PostgreSQL 可选表结构",
    "docker-compose.yml": "可选本地拓扑",
}

TASK_BY_PREFIX = [
    ("README.md", "T1"),
    ("package.json", "T1"),
    (".gitignore", "T1"),
    (".env.example", "T1"),
    ("docs/", "T1"),
    ("lib/", "T2"),
    ("services/question-service", "T3"),
    ("services/game-service", "T4"),
    ("services/user-service", "T5"),
    ("apps/web/admin", "T6"),
    ("apps/web", "T6"),
    ("tests/", "T7"),
    ("sql/", "T7"),
    ("docker-compose.yml", "T7"),
]


def sample_root() -> Path:
    candidates: list[Path] = []
    here = Path(__file__).resolve()
    candidates.append(here.parent.parent / "samples" / SAMPLE_DIR_NAME)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "space_code_agent" / "samples" / SAMPLE_DIR_NAME)
        candidates.append(Path(meipass) / "samples" / SAMPLE_DIR_NAME)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("内置 Space Fractions 样例缺失：" + " | ".join(str(c) for c in candidates))


def iter_sample_files() -> list[tuple[str, str]]:
    root = sample_root()
    files: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in {".agent_state", "node_modules", "__pycache__", ".git"} for part in path.parts):
            continue
        files.append((relative, path.read_text(encoding="utf-8")))
    files.sort(key=lambda item: _sort_key(item[0]))
    return files


def _sort_key(path: str) -> tuple[int, str]:
    for index, (prefix, _task) in enumerate(TASK_BY_PREFIX):
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return (index, path)
    return (len(TASK_BY_PREFIX), path)


def _task_for(path: str) -> str:
    for prefix, task in TASK_BY_PREFIX:
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return task
    return "T7"


def build_sample_plan(requirements: NormalizedRequirements) -> ProjectPlan:
    files = [
        PlanFile(
            path=path,
            purpose=PURPOSES.get(path, f"{path} 的实现文件"),
            task_id=_task_for(path),
            requirement_ids=REQUIREMENT_MAP.get(path, []),
        )
        for path, _content in iter_sample_files()
    ]
    return ProjectPlan(
        project_name=requirements.project_name or "Space Fractions",
        summary=(
            "按架构文档的 Game/Question/User 组件边界实现 Space Fractions："
            "三个零依赖 Node.js REST 服务、学生在浏览器完成答题与计分、"
            "教师后台维护题库，并提供单元/集成/端到端测试。"
        ),
        architecture_style="microservices (3 services, reduced infrastructure)",
        stack={
            "language": "JavaScript (CommonJS)",
            "runtime": "Node.js >= 20",
            "framework": "node:http (zero-dependency REST)",
            "persistence": "in-memory repositories; PostgreSQL DDL provided as optional adapter",
            "testing": "node:test + node:assert/strict",
            "frontend": "semantic HTML + CSS + ES modules (no build step)",
        },
        deviations=[
            Deviation(
                decision="以 node:http 替代 Express.js",
                reason="让生成项目零运行时依赖、可离线安装与验证。",
                impact="保留 REST 契约与中间件式路由，不使用 Express 生态中间件。",
            ),
            Deviation(
                decision="内存仓库替代在线 PostgreSQL",
                reason="演示环境不提供数据库；测试必须可重复。",
                impact="重启后数据丢失；sql/init.sql 提供持久化表结构与索引。",
            ),
            Deviation(
                decision="不部署 Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform",
                reason="架构文档未给出这些组件的业务约束与运维预算。",
                impact="仅保留微服务边界，不声称生产可用；列入 ASSUMPTIONS 的重大偏离。",
            ),
            Deviation(
                decision="最小 HMAC 管理员令牌替代完整 OAuth2",
                reason="教学演示的认证边界，避免引入外部身份提供商。",
                impact="无刷新令牌、无第三方登录；令牌有过期时间与签名校验。",
            ),
        ],
        tasks=[
            PlanTask(id="T1", title="文档与工程骨架", description="README、依赖声明、假设、目录",
                     requirement_ids=["FR-1", "NFR-1", "ASR-1", "ASR-2"],
                     acceptance=["README 可读", "package.json 有效", "ASSUMPTIONS 列出偏离"]),
            PlanTask(id="T2", title="共享 HTTP 工具", description="路由、JSON、CORS、服务器生命周期",
                     depends_on=["T1"], requirement_ids=["NFR-1"],
                     acceptance=["单元测试覆盖路由与 JSON 错误"]),
            PlanTask(id="T3", title="题库服务", description="种子题库、校验、公开/内部/管理员接口",
                     depends_on=["T2"], requirement_ids=["FR-DERIVED-2", "ASR-1", "ASR-2"],
                     acceptance=["公开接口隐藏答案", "管理员 CRUD 通过测试"]),
            PlanTask(id="T4", title="游戏服务", description="回合创建、顺序答题、计分、结果",
                     depends_on=["T3"], requirement_ids=["FR-1", "FR-DERIVED-1", "NFR-1"],
                     acceptance=["满分流程与错题流程通过测试"]),
            PlanTask(id="T5", title="用户服务", description="访客会话、管理员登录、令牌校验",
                     depends_on=["T2"], requirement_ids=["ASR-2"],
                     acceptance=["登录/过期/篡改令牌测试通过"]),
            PlanTask(id="T6", title="学生端与教师后台", description="引导、菜单、答题、得分、帮助、题库管理",
                     depends_on=["T4", "T5"], requirement_ids=["FR-1", "FR-DERIVED-1",
                                                                "FR-DERIVED-2", "FR-DERIVED-3"],
                     acceptance=["页面可静态访问", "无外部前端依赖"]),
            PlanTask(id="T7", title="测试、端到端与部署资料", description="跨服务流程测试、SQL、compose",
                     depends_on=["T6"], requirement_ids=["FR-1", "ASR-1", "NFR-1"],
                     acceptance=["node --test 全绿", "e2e 满分流程通过"]),
        ],
        files=files,
        verification_steps=[
            "node --check 所有 JS 文件（由 Agent 静态检查执行）",
            "node --test 单元/集成测试",
            "node --test tests/e2e 跨服务流程",
            "检查公开题目接口不泄露 answerIndex",
        ],
        assumptions=[assumption.text for assumption in requirements.assumptions],
        risks=[
            "内存数据在进程重启后丢失，属演示取舍。",
            "完整 OAuth2、PostgreSQL 集群与云原生组件未实现，已在 ASM-06 记录。",
        ],
        source="sample",
    )


def build_mock_script(requirements: NormalizedRequirements) -> list[ProviderResponse]:
    """One write_file call per sample file, then inspect and finish."""
    script: list[ProviderResponse] = []
    for path, content in iter_sample_files():
        script.append(tool_response([(
            "write_file",
            {
                "path": path,
                "content": content,
                "requirement_ids": REQUIREMENT_MAP.get(path, []),
            },
        )]))
    script.append(tool_response([(
        "inspect_project",
        {"checks": ["structure", "json", "links"]},
    )]))
    summary = (
        "已生成 Space Fractions：3 个零依赖 Node.js 服务（题库/游戏/用户）、"
        "学生端与教师后台、单元/集成/端到端测试、PostgreSQL 可选 DDL 与 Docker Compose。"
        "架构偏离：node:http 替代 Express，内存仓库替代在线 PostgreSQL，"
        "未部署 Redis/RabbitMQ/ES/K8s/Istio/Vault/Terraform，详见 docs/ASSUMPTIONS.md。"
    )
    script.append(tool_response([("finish_task", {"summary": summary})]))
    return script
