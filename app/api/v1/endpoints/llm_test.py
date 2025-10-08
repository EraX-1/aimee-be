"""
LLMサービスのテストエンドポイント
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ollama_service import OllamaService
from app.services.integrated_llm_service import IntegratedLLMService
from app.services.chroma_service import ChromaService
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


class RAGSearchRequest(BaseModel):
    query: str
    business_id: Optional[str] = None
    process_id: Optional[str] = None
    location_id: Optional[str] = None
    n_results: int = 5


class RAGSearchResponse(BaseModel):
    query: str
    recommended_operators: list
    total_documents: int
    search_time_ms: float


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


@router.post("/rag-search", response_model=RAGSearchResponse)
async def rag_search(request: RAGSearchRequest):
    """RAG検索専用エンドポイント（ChromaDBセマンティック検索）"""
    try:
        import time
        start_time = time.time()

        chroma_service = ChromaService()

        # 工程が指定されている場合は最適なオペレータを検索
        if request.business_id and request.process_id:
            app_logger.info(
                f"RAG検索: 業務{request.business_id}の工程{request.process_id}に最適なオペレータを検索"
            )
            operators = chroma_service.find_best_operators_for_process(
                business_id=request.business_id,
                process_id=request.process_id,
                location_id=request.location_id,
                n_results=request.n_results
            )
        else:
            # 汎用セマンティック検索
            app_logger.info(f"RAG検索: '{request.query}' のセマンティック検索")
            results = chroma_service.query_similar(
                query_text=request.query,
                n_results=request.n_results
            )

            # 結果を整形
            operators = []
            for i, doc in enumerate(results.get("documents", [])):
                metadata = results.get("metadatas", [])[i] if i < len(results.get("metadatas", [])) else {}
                distance = results.get("distances", [])[i] if i < len(results.get("distances", [])) else 0

                operators.append({
                    "document": doc,
                    "metadata": metadata,
                    "relevance_score": round(1 - distance, 4)
                })

        # 統計情報
        stats = chroma_service.get_collection_stats()
        search_time_ms = round((time.time() - start_time) * 1000, 2)

        return RAGSearchResponse(
            query=request.query,
            recommended_operators=operators,
            total_documents=stats.get("total_documents", 0),
            search_time_ms=search_time_ms
        )

    except Exception as e:
        app_logger.error(f"Error in RAG search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))