#!/usr/bin/env bash
# 停止服务
echo "停止 AI 智能问诊系统..."
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
echo "✅ 已停止"
