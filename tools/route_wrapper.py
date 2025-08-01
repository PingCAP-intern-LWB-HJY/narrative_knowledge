import tempfile
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from fastapi import UploadFile
import json

from tools.api_integration import PipelineAPIIntegration
from tools.base import ToolResult
from llm.factory import LLMInterface
from llm.embedding import get_text_embedding

class ToolsRouteWrapper:
    """
    Route wrapper that converts FastAPI's UploadFile to a format processable by the tools system
    """
    
    def __init__(self, session_factory=None):
        self.api_integration = PipelineAPIIntegration(session_factory)
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def process_upload_request(
        self,
        files: Union[UploadFile, List[UploadFile]],
        metadata: Union[str, Dict[str, Any]],
        process_strategy: Optional[Union[str, Dict[str, Any]]] = None,
        target_type: str = "knowledge_graph",
        llm_client=None,
        embedding_func=None
    ) -> ToolResult:
        """
        Route wrapper function: Process file upload requests
        
        Args:
            files: FastAPI UploadFile object or list
            metadata: Metadata (can be JSON string or dict)
            process_strategy: Processing strategy (can be JSON string or dict)
            target_type: Target type
            llm_client: LLM client (optional, will auto-create)
            embedding_func: Embedding function (optional, will auto-create)
            
        Returns:
            ToolResult: Processing result
        """
        prepared_files = []
        try:
            # 1. 标准化输入参数
            files_list = files if isinstance(files, list) else [files]
            parsed_metadata = self._parse_metadata(metadata)
            parsed_strategy = self._parse_process_strategy(process_strategy)
            
            # 2. 创建默认的 LLM 和 embedding 函数
            if llm_client is None:
                llm_client = LLMInterface
            if embedding_func is None:
                embedding_func = get_text_embedding
            
            # 3. 保存文件到临时目录并准备文件信息
            prepared_files = self._prepare_files(files_list, parsed_metadata)
            
            # 4. 构建 request_data
            request_data = self._build_request_data(
                target_type, parsed_metadata, parsed_strategy, 
                llm_client, embedding_func
            )
            
            # 5. 调用 tools 系统
            result = self.api_integration.process_request(
                request_data=request_data,
                files=prepared_files
            )
            
            return result
            
        except Exception as e:
            # 返回标准化的错误结果
            return ToolResult(
                success=False,
                error_message=f"Route wrapper error: {str(e)}",
                data={}
            )
        finally:
            # 清理临时文件
            self._cleanup_temp_files(prepared_files)

    def process_json_request(
        self,
        input_data: Any,
        metadata: Union[str, Dict[str, Any]],
        process_strategy: Optional[Union[str, Dict[str, Any]]] = None,
        target_type: str = "personal_memory",
        llm_client=None,
        embedding_func=None
    ) -> ToolResult:
        """
        Route wrapper function: Process JSON data requests (e.g., chat logs)
        
        Args:
            input_data: Input data (chat logs, text, etc.)
            metadata: Metadata
            process_strategy: Processing strategy
            target_type: Target type
            llm_client: LLM client
            embedding_func: Embedding function
            
        Returns:
            ToolResult: Processing result
        """
        try:
            # 1. 解析参数
            parsed_metadata = self._parse_metadata(metadata)
            parsed_strategy = self._parse_process_strategy(process_strategy)
            
            # 2. 创建默认客户端
            if llm_client is None:
                llm_client = LLMInterface("openai", model="gpt-4o")
            if embedding_func is None:
                embedding_func = get_text_embedding
            
            # 3. 构建 request_data
            request_data = self._build_request_data(
                target_type, parsed_metadata, parsed_strategy,
                llm_client, embedding_func
            )
            
            # 4. 添加输入数据
            if target_type == "personal_memory":
                request_data["chat_messages"] = input_data
                request_data["user_id"] = parsed_metadata.get("user_id")
            else:
                request_data["input"] = input_data
            
            # 5. 调用 tools 系统（无文件）
            result = self.api_integration.process_request(
                request_data=request_data,
                files=[]
            )
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                error_message=f"JSON request error: {str(e)}",
                data={}
            )

    def _parse_metadata(self, metadata: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse metadata"""
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in metadata: {e}")
        return metadata or {}

    def _parse_process_strategy(self, process_strategy: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Parse processing strategy"""
        if process_strategy is None:
            return {}
        if isinstance(process_strategy, str):
            try:
                return json.loads(process_strategy)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in process_strategy: {e}")
        return process_strategy

    def _prepare_files(self, files: List[UploadFile], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare file information"""
        prepared_files = []
        
        for i, file in enumerate(files):
            # 保存文件到临时目录
            temp_file_path = self.temp_dir / f"{i}_{file.filename}"
            
            # 读取文件内容并保存
            file_content = file.file.read()
            with open(temp_file_path, "wb") as f:
                f.write(file_content)
            
            # 重置文件指针（如果需要重复读取）
            file.file.seek(0)
            
            # 构建文件信息
            file_info = {
                "path": str(temp_file_path),
                "filename": file.filename,
                "metadata": {},  # 文件特定元数据
                "link": metadata.get("link", ""),
                "content_type": file.content_type,
                "size": len(file_content)
            }
            
            prepared_files.append(file_info)
        
        return prepared_files

    def _build_request_data(
        self, 
        target_type: str, 
        metadata: Dict[str, Any], 
        process_strategy: Dict[str, Any],
        llm_client, 
        embedding_func
    ) -> Dict[str, Any]:
        """Build request data"""
        return {
            "target_type": target_type,
            "metadata": metadata,
            "process_strategy": process_strategy,
            "llm_client": llm_client,
            "embedding_func": embedding_func,
            "force_regenerate": metadata.get("force_regenerate", False)
        }

    def _cleanup_temp_files(self, prepared_files: List[Dict[str, Any]]):
        """Cleanup temporary files"""
        for file_info in prepared_files:
            try:
                temp_path = Path(file_info["path"])
                if temp_path.exists():
                    temp_path.unlink()
            except Exception as e:
                # 日志记录但不抛出异常
                print(f"Warning: Failed to cleanup temp file {file_info['path']}: {e}")

    def __del__(self):
        """Cleanup temporary directory"""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass