"""
LLMサービスのテストエンドポイント
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ollama_service import OllamaService
from app.services.integrated_llm_service import IntegratedLLMService
from app.db.session import get_db
from app.core.logging import app_logger

router = APIRouter()


class TestIntentRequest(BaseModel):
    message: str


class TestIntentResponse(BaseModel):
    intent: Dict[str, Any]
    response: str
    

class IntegratedTestRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    detail: bool = False


class IntegratedTestResponse(BaseModel):
    response: str
    intent: Dict[str, Any]
    suggestion: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]
    debug_info: Optional[Dict[str, Any]] = None
    
    
class ConnectionTestResponse(BaseModel):
    light_llm: bool
    main_llm: bool
    message: str


@router.get("/connection", response_model=ConnectionTestResponse)
async def test_llm_connection():
    """LLMサービスへの接続をテスト"""
    service = OllamaService()
    results = await service.test_connection()
    
    all_connected = all(results.values())
    message = "すべてのLLMサービスが正常に接続されています。" if all_connected else "一部のLLMサービスに接続できません。"
    
    return ConnectionTestResponse(
        light_llm=results["light_llm"],
        main_llm=results["main_llm"],
        message=message
    )


@router.post("/intent", response_model=TestIntentResponse)
async def test_intent_analysis(request: TestIntentRequest):
    """意図解析のテスト"""
    try:
        service = OllamaService()
        
        # 意図解析
        app_logger.info(f"Analyzing intent for: {request.message}")
        intent = await service.analyze_intent(request.message)
        
        # レスポンス生成
        app_logger.info(f"Generating response with intent: {intent}")
        response = await service.generate_response(request.message, intent)
        
        return TestIntentResponse(
            intent=intent,
            response=response
        )
        
    except Exception as e:
        app_logger.error(f"Error in intent analysis test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/integrated", response_model=IntegratedTestResponse)
async def test_integrated_llm(
    request: IntegratedTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """統合LLMサービスのテスト（意図解析＋DB照会＋レスポンス生成）"""
    try:
        service = IntegratedLLMService()
        
        # 統合処理を実行
        app_logger.info(f"Processing integrated request: {request.message}")
        result = await service.process_message(
            message=request.message,
            context=request.context,
            db=db,
            detail=request.detail
        )
        
        return IntegratedTestResponse(**result)
        
    except Exception as e:
        app_logger.error(f"Error in integrated LLM test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))