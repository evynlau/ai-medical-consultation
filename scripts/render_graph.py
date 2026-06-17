#!/usr/bin/env python
"""渲染 MedicalAgent 的 LangGraph 三张图为 Mermaid

用法:
    cd backend && venv/bin/python ../scripts/render_graph.py [output_dir]

输出:
    output_dir/chat_graph.mmd
    output_dir/analyze_graph.mmd
    output_dir/triage_graph.mmd
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 让脚本可以从项目根或 backend 目录直接运行
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.agents.graph import get_analyze_graph, get_chat_graph, get_triage_graph  # noqa: E402


def render(name: str, graph, out_dir: Path) -> Path:
    mermaid = graph.get_graph().draw_mermaid()
    out = out_dir / f"{name}.mmd"
    out.write_text(mermaid, encoding="utf-8")
    print(f"  ✓ {name} → {out}")
    return out


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"📐 渲染 LangGraph 到: {out_dir}")
    render("chat_graph", get_chat_graph(), out_dir)
    render("analyze_graph", get_analyze_graph(), out_dir)
    render("triage_graph", get_triage_graph(), out_dir)
    print("✅ 完成。可把 .mmd 贴到 https://mermaid.live 预览。")


if __name__ == "__main__":
    main()
