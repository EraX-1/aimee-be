#!/usr/bin/env python3
"""
Ollama接続テストスクリプト
"""
import asyncio
import httpx
import os

# ローカル環境用の設定
os.environ["OLLAMA_LIGHT_HOST"] = "localhost"
os.environ["OLLAMA_LIGHT_PORT"] = "11433"
os.environ["OLLAMA_MAIN_HOST"] = "localhost"  
os.environ["OLLAMA_MAIN_PORT"] = "11434"

# サービスをインポート
from app.services.ollama_service import OllamaService


async def test_ollama():
    service = OllamaService()
    
    print("🔍 Ollama接続テスト")
    print(f"Light URL: {service.light_base_url}")
    print(f"Main URL: {service.main_base_url}")
    print()
    
    # 接続テスト
    print("1️⃣ 接続確認...")
    connection_status = await service.test_connection()
    print(f"  軽量LLM: {'✅' if connection_status['light_llm'] else '❌'}")
    print(f"  メインLLM: {'✅' if connection_status['main_llm'] else '❌'}")
    print()
    
    # 意図解析テスト
    if connection_status['light_llm']:
        print("2️⃣ 意図解析テスト...")
        message = "札幌のエントリ1工程が遅延しています。対応策を提案してください。"
        intent = await service.analyze_intent(message)
        print(f"  入力: {message}")
        print(f"  意図タイプ: {intent.get('intent_type')}")
        print(f"  緊急度: {intent.get('urgency')}")
        print(f"  エンティティ: {intent.get('entities')}")
        print()
    
    # レスポンス生成テスト
    if connection_status['main_llm'] and intent:
        print("3️⃣ レスポンス生成テスト...")
        response = await service.generate_response(message, intent)
        print(f"  レスポンス（最初の200文字）:")
        print(f"  {response[:200]}...")


if __name__ == "__main__":
    asyncio.run(test_ollama())