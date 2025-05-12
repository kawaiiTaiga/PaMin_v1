from typing import Dict, Any, Optional

# 상대 경로 임포트
from ..core.models import GraphState

def set_final_result_node(state: GraphState) -> Dict[str, Optional[str]]:
    """ 수렴 노드에서 선택된 ID를 최종 결과 필드에 저장하는 간단한 노드 """
    print("\n--- 최종 결과 저장 단계 ---")
    final_id = state.get('selected_idea_id')
    print(f"  최종 선택된 ID: {final_id}")
    return {"final_selected_tmi_id": final_id}