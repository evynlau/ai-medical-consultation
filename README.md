# AI 智能问诊系统

> 基于 **LLM + Agent + RAG** 的医疗问诊平台,7×24h 提供智能症状分析、知识检索、智能分诊、多轮对话,并配备完整的管理后台与医生人工回复能力。

![tech](https://img.shields.io/badge/Python-3.10%2B-blue)
![tech](https://img.shields.io/badge/Vue-3.4-green)
![tech](https://img.shields.io/badge/FastAPI-0.109-009688)
![tech](https://img.shields.io/badge/Element_Plus-2.5-409EFF)
![role](https://img.shields.io/badge/患者端-✅-blue)
![role](https://img.shields.io/badge/管理后台-✅-blue)
![role](https://img.shields.io/badge/医生回复-✅-blue)

---

## ✨ 核心能力

### 👤 患者端
| 模块 | 说明 |
|---|---|
| 🤖 **智能问诊** | 多轮对话收集症状,AI 分析可能的病因 |
| 📋 **结构化分析** | 一键输出 JSON 报告(紧急度/可能病因/检查/科室/护理),并自动写回问诊 |
| 🏥 **智能分诊** | 根据症状推荐就诊科室,判断紧急程度 |
| 📚 **知识库检索** | 基于 FAISS 向量数据库的医学知识精准检索 |
| 🚨 **紧急识别** | 识别胸痛、呼吸困难等紧急症状,优先提示就医 |
| 💾 **问诊记录** | 持久化存储问诊历史,支持回溯查看 |

### 👨⚕️ 管理后台(独立 `/admin` 路由)
| 模块 | 说明 |
|---|---|
| 📊 **数据概览** | 8 张指标卡 + 近 7 日问诊趋势 + 知识库分类分布 |
| 📋 **问诊管理** | 全平台问诊,可按紧急度/状态/关键词筛选,详情含完整对话流 |
| 🚨 **紧急看板** | 自动高亮 urgency≥4 的活跃问诊,一键跳转处理 |
| 👥 **用户管理** | 设置/取消管理员、医生、科室,封禁/解封账号 |
| 📚 **知识库管理** | 增删改查 + 一键重建 FAISS 索引 |
| 💬 **医生人工回复** | 医生可对 AI 答案进行专业修正,自动结束问诊 |

---

## 🛠️ 技术栈

- **后端**:FastAPI 0.109 + SQLAlchemy 2.0(async) + LangChain + FAISS-cpu
- **前端**:Vue 3 + Composition API + Pinia + Element Plus + Vite + Axios
- **AI**:OpenAI 兼容 LLM(支持 GPT-4 / 通义千问 / 智谱 / DeepSeek / **Ollama 本地**)
- **数据库**:SQLite(默认) / PostgreSQL(可选)
- **缓存**:Redis(可选)
- **认证**:JWT,角色分层(用户/医生/管理员)

---

## 📁 项目结构

```
AI智能问诊系统/
├── backend/                              # FastAPI 后端
│   ├── main.py                           # 应用入口
│   ├── requirements.txt                  # Python 依赖
│   ├── .env.example                      # 环境变量示例
│   ├── Dockerfile
│   └── app/
│       ├── core/                         # 配置/数据库/安全/lifespan
│       ├── models/                       # ORM(User/Consultation/Message/Knowledge)
│       ├── schemas/                      # Pydantic Schemas
│       ├── services/                     # Embedding / RAG / LLM(三种 provider)
│       ├── agents/                       # Medical Agent(症状分析/分诊/紧急识别)
│       ├── api/
│       │   ├── v1/
│       │   │   ├── user.py               # 用户注册/登录
│       │   │   ├── consult.py            # 问诊 CRUD + 消息
│       │   │   ├── agent.py              # 症状分析/分诊
│       │   │   ├── knowledge.py          # 知识库公开 CRUD
│       │   │   └── admin.py              # 管理后台(仪表盘/问诊/紧急/用户/知识/医生回复)
│       │   └── ws/                       # WebSocket 实时对话
│       └── utils/                        # logger
│
├── frontend/                             # Vue3 前端
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile + nginx.conf
│   └── src/
│       ├── api/                          # axios(http/user/consult/agent/knowledge/admin)
│       ├── stores/                       # Pinia(user/chat)
│       ├── router/                       # 含 /admin 路由守卫
│       ├── views/
│       │   ├── Home.vue                  # 首页
│       │   ├── Chat.vue                  # 问诊
│       │   ├── History.vue               # 历史
│       │   ├── Knowledge.vue             # 知识库(患者)
│       │   ├── Login.vue
│       │   └── admin/                    # 管理后台 6 个页面
│       │       ├── AdminLayout.vue
│       │       ├── Dashboard.vue
│       │       ├── Consultations.vue     # 含医生回复表单
│       │       ├── Emergency.vue
│       │       ├── KnowledgeAdmin.vue
│       │       └── Users.vue
│       └── styles/
│
├── knowledge_base/                       # 医学知识库 16 篇 Markdown
│   ├── diseases/    7 篇                 # 感冒/胃肠炎/高血压/偏头痛/冠心病/糖尿病/过敏性鼻炎
│   ├── drugs/       4 篇                 # 对乙酰氨基酚/布洛芬/二甲双胍/阿莫西林
│   ├── examinations/ 2 篇                # 血常规/心电图
│   └── guidelines/  3 篇                 # 感冒用药/胸痛识别/急救电话
│
├── scripts/
│   ├── init_kb.py                        # 知识库入库脚本
│   ├── start.sh                          # 一键启动
│   └── stop.sh
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 快速开始

### 默认账号

| 账号 | 密码 | 角色 | 入口 |
|---|---|---|---|
| `admin` | `admin123` | 超级管理员 | http://localhost:5173/admin |
| `dr_zhang` | `doctor123` | 医生(心血管内科) | 可在管理后台回复问诊 |

> 第一次启动时,如果数据库为空,可手动创建以上账号(参见下方 "创建管理员/医生")。

### 方式一:一键脚本(Mac/Linux)

```bash
cd /home/evynlau/桌面/AI-Agent/AI智能问诊系统
./scripts/start.sh
```

脚本自动:
1. 创建 Python 虚拟环境 + 安装依赖
2. 创建 `.env`(默认 mock LLM,无需 Key)
3. 导入知识库到 SQLite + 构建 FAISS 索引
4. 启动后端 (http://localhost:8000)
5. 启动前端 (http://localhost:5173)

### 方式二:Docker Compose

```bash
cd /home/evynlau/桌面/AI-Agent/AI智能问诊系统
cp .env.example .env
# 编辑 .env 配置 LLM / Key(可选)
docker-compose up -d
```

### 方式三:手动启动

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python ../scripts/init_kb.py
uvicorn main:app --reload --port 8000

# 前端(新终端)
cd frontend
npm install
npm run dev
```

---

## ⚙️ 配置说明(`backend/.env`)

### LLM 三种模式

| `LLM_PROVIDER` | 说明 | 适用 |
|---|---|---|
| `mock` | 内置规则引擎 + 模板,无需任何服务 | 先跑通流程、调试 |
| `ollama` | 本地 Ollama(自动用 `http://localhost:11434/v1`) | 本地推理、隐私 |
| `openai` | OpenAI 兼容服务 | 云端 API |

**Ollama 配置(推荐本地开发)**:
```bash
LLM_PROVIDER=ollama
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=gemma4:e2b              # 推荐非思考型,7GB,启动快
```

**OpenAI 兼容云服务**:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
```

| 服务 | BASE_URL | 推荐模型 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4-turbo-preview` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` / `qwen-max` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Ollama | `http://localhost:11434/v1` | `gemma4:e2b` / `glm-4.7-flash` |

> ⚠️ **避免思考型 MoE 模型**(`qwen3.6:35b-a3b` 等),它们有时只输出 `reasoning` 字段不输出 `content`,本系统已自动检测并降级,但体验更推荐非思考型。

### Embedding 三种模式

| `EMBEDDING_PROVIDER` | 说明 |
|---|---|
| `mock` | 字符 hash 简易向量,**零依赖**(默认,推荐本地演示) |
| `local` | sentence-transformers 本地模型(首次需下载 ~120MB) |
| `openai` | OpenAI `text-embedding-3-small` |

### 创建管理员/医生账号

启动后,在 `backend/` 目录下运行:

```python
python3 << 'PYEOF'
import asyncio, sys, bcrypt
sys.path.insert(0, '.')
from app.core.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        # 管理员
        a = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if not a:
            pw = "admin123"
            db.add(User(username="admin", email="admin@medical.com",
                hashed_password=bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode(),
                full_name="系统管理员", is_admin=True, is_active=True))
            print(f"✅ 创建 admin / {pw}")
        # 医生
        z = (await db.execute(select(User).where(User.username == "dr_zhang"))).scalar_one_or_none()
        if not z:
            pw = "doctor123"
            db.add(User(username="dr_zhang", email="zhang@hospital.com",
                hashed_password=bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode(),
                full_name="张医生", is_doctor=True, specialty="心血管内科", is_active=True))
            print(f"✅ 创建医生 dr_zhang / {pw}")
        await db.commit()
asyncio.run(main())
PYEOF
```

---

## 🎬 三种角色完整工作流

### 👤 患者流程

```
1. 访问 http://localhost:5173  → 首页
2. 点 "立即开始问诊" 或选 "常见症状"
3. 在对话中描述症状(可匿名)
4. AI 问:"持续多久了?有无伴随?既往病史?用过什么药?"
5. 答完后点 "结构化分析" → 弹出报告
   同时自动同步到问诊记录(紧急度/科室/分析消息)
6. 右上角点 "问诊记录" → 查看历史
```

### 👨⚕️ 医生流程(在管理后台)

```
1. 访问 http://localhost:5173/admin
2. 用 dr_zhang / doctor123 登录
3. 左侧菜单 → "问诊管理" → 看到所有患者问诊
4. 点某条问诊 → 弹出详情(患者信息 + 完整对话)
5. 在"医生回复"表单里:
   - 填诊断意见(可选)
   - 选覆盖紧急度(可选)
   - 写专业回复
6. 点 "提交回复并结束问诊"
   → 问诊自动标 closed,患者端看到医生消息
```

### 🛡️ 管理员流程

```
1. 访问 http://localhost:5173/admin
2. 用 admin / admin123 登录
3. "数据概览" → 看 8 张指标卡 + 趋势图
4. "紧急看板" → 重点处理 urgency≥4 的活跃问诊
5. "问诊管理" → 全平台筛选(紧急度/状态/关键词)
6. "知识库管理" → 新增/编辑/删除知识,一键 reindex
7. "用户管理" → 改角色(管理员/医生)、设科室、封禁
```

---

## 📚 知识库管理

### 内置 16 篇(4 类)

- **疾病** (7):感冒、急性胃肠炎、高血压、偏头痛、冠心病、糖尿病、过敏性鼻炎
- **药品** (4):对乙酰氨基酚、布洛芬、二甲双胍、阿莫西林
- **检查** (2):血常规、心电图
- **指南** (3):感冒用药、胸痛识别、急救电话

### 添加新知识(三种方式)

**方式 1:Markdown 文件**
1. 在 `knowledge_base/diseases/` 创建 `.md`
2. 第一个 `#` 标题作为知识标题
3. 重启或手动 init:
   ```bash
   cd backend && source venv/bin/activate
   python ../scripts/init_kb.py
   ```

**方式 2:API(管理员)**
```bash
curl -X POST http://localhost:8000/api/v1/admin/knowledge \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"...","category":"disease","content":"...","tags":"...","source":"..."}'
```

**方式 3:管理后台 UI**
→ 知识库管理 → 新增知识 → 填表 → 保存(自动重建索引)

### 重建索引

```bash
curl -X POST http://localhost:8000/api/v1/admin/knowledge/reindex \
  -H "Authorization: Bearer <admin_token>"
```

---

## 🔌 API 速览

完整文档(OpenAPI):**http://localhost:8000/docs**

### 患者端公开 API

| Method | Path | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/api/v1/user/register` | ❌ | 注册 |
| POST | `/api/v1/user/login` | ❌ | 登录 |
| GET | `/api/v1/user/me` | ✅ | 我的资料 |
| PUT | `/api/v1/user/me` | ✅ | 修改资料 |
| POST | `/api/v1/consult` | ❌ | 创建问诊(可匿名) |
| GET | `/api/v1/consult` | ✅ | 我的问诊列表 |
| GET | `/api/v1/consult/{id}` | 可选 | 问诊详情 |
| POST | `/api/v1/consult/{id}/messages` | 可选 | 发送消息 |
| POST | `/api/v1/consult/{id}/close` | 可选 | 结束问诊 |
| POST | `/api/v1/agent/analyze` | ❌ | 结构化分析(可选 `consultation_id` 自动同步) |
| POST | `/api/v1/agent/triage` | ❌ | 快速分诊 |
| GET | `/api/v1/knowledge` | ❌ | 知识库列表 |
| GET | `/api/v1/knowledge/search/query?q=` | ❌ | 知识语义检索 |
| WS | `/api/ws/chat` | ❌ | 实时流式对话 |

### 管理后台 API(需 admin token)

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/admin/stats` | 仪表盘统计 |
| GET | `/api/v1/admin/consultations` | 全平台问诊列表(可筛选) |
| GET | `/api/v1/admin/consultations/{id}` | 问诊详情(含患者信息) |
| POST | `/api/v1/admin/consultations/{id}/reply` | **医生回复**(需 doctor 或 admin) |
| GET | `/api/v1/admin/emergency` | 紧急病例列表 |
| GET | `/api/v1/admin/users` | 用户列表 |
| PUT | `/api/v1/admin/users/{id}` | 修改用户角色/状态 |
| POST | `/api/v1/admin/knowledge` | 新增知识 |
| PUT | `/api/v1/admin/knowledge/{id}` | 编辑知识 |
| DELETE | `/api/v1/admin/knowledge/{id}` | 删除知识 |
| POST | `/api/v1/admin/knowledge/reindex` | 重建向量索引 |

### 示例:结构化分析并自动同步

```bash
# 1. 登录拿 token
TOK=$(curl -s -X POST http://localhost:8000/api/v1/user/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. 创建问诊
CID=$(curl -s -X POST http://localhost:8000/api/v1/consult \
  -H "Content-Type: application/json" \
  -d '{"chief_complaint":"胸痛 1 小时,大汗淋漓"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "问诊 ID: $CID"

# 3. 结构化分析(传 consultation_id → 自动写回)
curl -s -X POST http://localhost:8000/api/v1/agent/analyze \
  -H "Content-Type: application/json" \
  -d "{\"symptoms\":\"胸痛 1 小时,大汗淋漓\",\"consultation_id\":$CID}"

# 4. 验证
curl -s http://localhost:8000/api/v1/consult/$CID | python3 -m json.tool
# 应当看到 urgency_level=4, recommended_department="心血管内科"
```

### 示例:医生人工回复

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/consultations/$CID/reply \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{
    "content":"根据您描述的胸痛伴大汗,建议立即拨打 120,到医院做心电图+心肌酶谱。",
    "override_urgency":4,
    "diagnosis":"疑似急性冠脉综合征,需立即排查"
  }'
# 问诊自动变为 closed
```

---

## 🧪 端到端测试

启动后,运行这套 curl 验证全链路:

```bash
# 1. 健康检查
curl http://localhost:8000/health

# 2. 创建问诊
curl -X POST http://localhost:8000/api/v1/consult \
  -H "Content-Type: application/json" \
  -d '{"chief_complaint":"头痛 3 天,伴有低烧 37.8 度"}'

# 3. 知识检索
curl "http://localhost:8000/api/v1/knowledge/search/query?q=%E5%A4%B4%E7%97%9B"

# 4. 结构化分析
curl -X POST http://localhost:8000/api/v1/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"symptoms":"胸痛 1 小时,大汗淋漓"}'

# 5. 智能分诊
curl -X POST http://localhost:8000/api/v1/agent/triage \
  -H "Content-Type: application/json" \
  -d '{"symptoms":"胃痛,饭后加重,反酸"}'

# 6. 用户注册(自动)
curl -X POST http://localhost:8000/api/v1/user/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@ex.com","password":"test123","age":30,"gender":"male"}'
```

---

## ⚠️ 重要免责声明

**本系统提供的所有健康建议仅供参考,不能替代专业医生诊断。**

如有以下紧急情况,**请立即拨打 120 或前往最近的医院急诊**:
- 剧烈胸痛、压榨性胸痛(伴大汗/左肩放射痛/濒死感)
- 呼吸困难、窒息感
- 大出血、咯血、呕血
- 突发剧烈头痛、神志不清、偏瘫(疑似中风)
- 严重外伤、车祸
- 自杀倾向

---

## 🐛 常见问题

**Q: 启动后访问前端 404?**
A: 前端在 5173,Vite 已代理 `/api` 到后端 8000,直接访问 http://localhost:5173。

**Q: admin / dr_zhang 账号不存在?**
A: 数据库是空的。运行上面的"创建管理员/医生"脚本。

**Q: 切换 Ollama 后 AI 回复 0 字符?**
A: 多半是**思考型 MoE 模型**(如 `qwen3.6:35b-a3b`)的 bug — 它把推理写在 `reasoning` 字段但 `content` 是空。换成非思考型如 `gemma4:e2b` 或 `glm-4.7-flash`。

**Q: 知识库 tab 报 422?**
A: 旧版本 limit 上限是 100,admin 后台需要 200+。已修复,上限改为 500。

**Q: 跑"结构化分析"后管理后台紧急看板没更新?**
A: 调用 `/analyze` 时必须传 `consultation_id`,系统才会把分析结果写回。前端 Chat.vue 已自动传。

**Q: 医生回复需要什么权限?**
A: `is_doctor=True` 或 `is_admin=True` 即可。可在管理后台 → 用户管理 设任意用户为医生。

**Q: 如何重置数据库?**
A:
```bash
rm -f backend/data/medical.db
rm -rf backend/data/faiss_index
# 然后重新跑 init_kb.py
```

**Q: 前端打包后访问空白?**
A: 检查 vite.config.js 的 `server.proxy` 配置 / nginx.conf 的反代。

**Q: 启动报错 "no module named app"?**
A: 必须在 `backend/` 目录下运行 uvicorn。

**Q: 如何看 LLM 是否真被调用?**
A: 启动日志会打印 `[LLM] 调用 openai 模型: gemma4:e2b @ http://localhost:11434/v1`,以及响应字符数。若看到 "降级到 mock",说明 LLM 调用失败。

---

## 🛣️ 路线图

- [x] 基础 RAG 问诊(患者端)
- [x] 真实 LLM 接入(OpenAI / Ollama / 多家兼容)
- [x] 结构化分析与紧急度自动同步
- [x] 管理后台(仪表盘/问诊/紧急/知识/用户)
- [x] 医生人工回复(覆盖 AI 答案)
- [ ] 多医生协同(转科会诊)
- [ ] 处方/检查报告 OCR
- [ ] 真实医院 HIS 系统对接
- [ ] 移动端 H5 / 小程序

---

## 📜 License

MIT
