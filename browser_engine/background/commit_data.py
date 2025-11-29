"""
Tab(Main Thread)에서 Browser(Browser Thread)로 전달되는 렌더링 데이터
"""
from dataclasses import dataclass, field
from typing import List, Any, Optional


@dataclass
class CommitData:
    """Tab이 렌더링을 완료한 후 Browser로 커밋하는 데이터"""

    # 그리기 명령 리스트 (display_list)
    display_list: List[Any] = field(default_factory=list)

    # 문서 전체 높이
    document_height: float = 0.0

    # 현재 스크롤 위치
    scroll: float = 0.0

    # 현재 URL (주소창 표시용)
    url: Optional[str] = None

    # 탭의 고유 ID
    tab_id: int = 0
