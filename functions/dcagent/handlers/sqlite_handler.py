# dcagent/handlers/sqlite_handler.py
from __future__ import annotations # 파일 맨 위 필수

import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
import os

# 상대 경로 임포트
from ..core.models import Idea
from ..core.db_interface import IdeaDBHandler # 인터페이스 임포트

class SQLiteHandler(IdeaDBHandler): # 명시적 상속
    def __init__(self, db_file: str):
        self.db_file = db_file
        db_dir = os.path.dirname(db_file)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_file)
        # 결과를 딕셔너리처럼 접근 가능하게 설정
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """ 데이터베이스 테이블 생성 (item_type 컬럼 추가) """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # item_type 컬럼 추가
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ideas (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        source_node TEXT,
                        generation_step INTEGER,
                        created_at TEXT NOT NULL,
                        metadata TEXT,
                        parent_id TEXT,
                        usage_count INTEGER DEFAULT 0,
                        item_type TEXT
                    )
                ''')
                # 필요시 인덱스 추가 (예: item_type, generation_step, usage_count)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_type ON ideas (item_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_gen_step ON ideas (generation_step)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_count ON ideas (usage_count)")
                conn.commit()
                print(f"[정보] SQLite DB '{self.db_file}' 초기화 완료 (item_type 컬럼 포함).")
        except sqlite3.Error as e:
            print(f"[오류] SQLite DB 초기화 실패: {e}")
            raise

    def _map_row_to_idea(self, row: sqlite3.Row) -> Optional[Idea]:
        """ DB row를 Idea Pydantic 모델 객체로 변환 (item_type 포함) """
        if not row:
            return None
        try:
            idea_data = dict(row) # Row 객체를 딕셔너리로 변환
            # metadata 처리 (JSON 문자열 -> dict)
            idea_data['metadata'] = json.loads(row['metadata']) if row['metadata'] else {}
            # created_at 처리 (ISO 문자열 -> datetime)
            idea_data['created_at'] = datetime.fromisoformat(row['created_at'])
            # item_type 필드는 그대로 매핑됨 (DB 스키마와 모델 필드 이름 동일)
            return Idea(**idea_data)
        except Exception as e:
            # 오류 발생 시 아이디어 ID와 함께 로그 출력 (디버깅 용이)
            row_id = row['id'] if 'id' in row.keys() else 'N/A' # sqlite3.Row는 키로 접근 가능
            print(f"[오류] DB row -> Idea 변환 실패 (ID: {row_id}): {e}")
            return None

    def save_ideas(self, ideas_data: List[Dict[str, Any]]) -> List[str]:
        """ 아이디어 목록을 DB에 저장 (item_type 포함) """
        saved_ids = []
        # 컬럼 9개에 맞춰 VALUES (?,?,?,?,?,?,?,?,?) 로 수정
        sql = 'INSERT INTO ideas (id, content, source_node, generation_step, created_at, metadata, parent_id, usage_count, item_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
        rows_to_insert: List[Tuple] = []

        for data in ideas_data:
            try:
                # 기본값 설정 및 Idea 객체 생성 (item_type 포함)
                idea = Idea(**data) # 이제 data 딕셔너리에 item_type이 있어야 함
                metadata_json = json.dumps(idea.metadata) if idea.metadata else None
                created_at_iso = idea.created_at.isoformat()

                # SQL 파라미터 순서에 맞게 튜플 생성
                rows_to_insert.append((
                    idea.id, idea.content, idea.source_node, idea.generation_step,
                    created_at_iso, metadata_json, idea.parent_id, idea.usage_count,
                    idea.item_type # item_type 추가
                ))
                saved_ids.append(idea.id)
            except Exception as e:
                print(f"[오류] 저장할 Idea 객체 생성 또는 데이터 준비 중 오류: {e} - 데이터: {data}")
                # 문제가 있는 데이터는 건너뛰고 계속 진행하거나, 전체 실패 처리 가능

        if not rows_to_insert:
            print("[정보] 저장할 아이디어가 없습니다.")
            return []

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, rows_to_insert)
                conn.commit()
            return saved_ids
        except sqlite3.Error as e:
            print(f"[오류] 아이디어 저장 실패 (executemany): {e}")
            # 실패 시 어떤 데이터에서 문제가 발생했는지 파악하기 어려울 수 있음
            return [] # 실패 시 빈 리스트 반환

    def get_ideas(self, idea_ids: List[str]) -> List[Idea]:
        # (기존 로직과 동일 - ID 목록으로 조회하므로 item_type 필터 불필요)
        if not idea_ids: return []
        placeholders = ', '.join('?' * len(idea_ids))
        sql = f'SELECT * FROM ideas WHERE id IN ({placeholders})'
        ideas: List[Idea] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, idea_ids)
                for row in cursor.fetchall():
                    idea = self._map_row_to_idea(row)
                    if idea: ideas.append(idea)
            return ideas
        except sqlite3.Error as e: print(f"[오류] 아이디어 목록 조회 실패: {e}"); return []

    def get_idea(self, idea_id: str) -> Optional[Idea]:
        # (기존 로직과 동일 - ID로 조회하므로 item_type 필터 불필요)
        sql = 'SELECT * FROM ideas WHERE id = ?'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (idea_id,))
                return self._map_row_to_idea(cursor.fetchone())
        except sqlite3.Error as e: print(f"[오류] 아이디어 단건 조회 실패 (ID: {idea_id}): {e}"); return None

    def increment_usage_count(self, idea_id: str) -> bool:
        # (기존 로직과 동일)
        sql = 'UPDATE ideas SET usage_count = usage_count + 1 WHERE id = ?'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (idea_id,))
                conn.commit()
                # 변경된 행이 있는지 확인 (ID가 존재했다면 1 이상)
                return cursor.rowcount > 0
        except sqlite3.Error as e: print(f"[오류] 사용 횟수 증가 실패 (ID: {idea_id}): {e}"); return False

    def clear_all_ideas(self) -> None:
         # (기존 로직과 동일)
         sql = 'DELETE FROM ideas'
         try:
             with self._get_connection() as conn:
                 cursor = conn.cursor()
                 cursor.execute(sql)
                 conn.commit()
             print("[정보] 데이터베이스의 모든 아이디어를 삭제했습니다.")
         except sqlite3.Error as e:
             print(f"[오류] DB 내용 삭제 실패: {e}")

    def get_ideas_by_step(self, step: int) -> List[Idea]:
         # (item_type 필터 추가 가능하지만, 일단 기존 로직 유지)
         sql = 'SELECT * FROM ideas WHERE generation_step = ?'
         ideas: List[Idea] = []
         try:
             with self._get_connection() as conn:
                 cursor = conn.cursor()
                 cursor.execute(sql, (step,))
                 rows = cursor.fetchall()
                 for row in rows:
                     idea = self._map_row_to_idea(row)
                     if idea: ideas.append(idea)
             return ideas
         except sqlite3.Error as e:
             print(f"[오류] 단계별 아이디어 조회 실패 (단계: {step}): {e}")
             return []

    def check_content_exists(self, contents: List[str]) -> Set[str]:
          # (기존 로직과 동일)
          if not contents: return set()
          existing_contents = set()
          placeholders = ', '.join('?' * len(contents))
          sql = f'SELECT DISTINCT content FROM ideas WHERE content IN ({placeholders})'
          try:
              with self._get_connection() as conn:
                  cursor = conn.cursor()
                  cursor.execute(sql, contents)
                  rows = cursor.fetchall()
                  for row in rows:
                      existing_contents.add(row['content'])
              return existing_contents
          except sqlite3.Error as e:
              print(f"[오류] 콘텐츠 존재 여부 확인 실패: {e}")
              return set()

    # --- item_type 필터링 기능 추가된 메소드 ---
    def check_ideas_exist(self,
                          generation_step: Optional[int] = None,
                          max_usage_count: Optional[int] = None,
                          item_type: Optional[str] = None # 추가됨
                          ) -> bool:
        """ 조건에 맞는 아이디어가 하나라도 존재하는지 확인 (item_type 필터 추가) """
        sql = "SELECT 1 FROM ideas WHERE 1=1" # 기본 쿼리
        params: List[Any] = []

        if generation_step is not None:
            sql += " AND generation_step = ?"
            params.append(generation_step)
        if max_usage_count is not None:
            # max_usage_count=1 이면 usage_count < 1 (즉, 0) 인 것을 찾음
            sql += " AND usage_count < ?"
            params.append(max_usage_count)
        if item_type is not None: # item_type 조건 추가
            sql += " AND item_type = ?"
            params.append(item_type)

        sql += " LIMIT 1" # 하나만 찾으면 되므로 LIMIT 1 추가

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"[오류] 아이디어 존재 여부 확인 실패 (조건: step={generation_step}, usage<{max_usage_count}, type={item_type}): {e}")
            return False

    def get_idea_ids(self,
                     generation_step: Optional[int] = None,
                     max_usage_count: Optional[int] = None,
                     item_type: Optional[str] = None # 추가됨
                     ) -> List[str]:
        """ 조건에 맞는 아이디어 ID 목록 반환 (item_type 필터 추가) """
        ids: List[str] = []
        sql = "SELECT id FROM ideas WHERE 1=1" # 기본 쿼리
        params: List[Any] = []

        if generation_step is not None:
            sql += " AND generation_step = ?"
            params.append(generation_step)
        if max_usage_count is not None:
            sql += " AND usage_count < ?"
            params.append(max_usage_count)
        if item_type is not None: # item_type 조건 추가
            sql += " AND item_type = ?"
            params.append(item_type)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                ids = [row['id'] for row in rows]
            return ids
        except sqlite3.Error as e:
            print(f"[오류] 아이디어 ID 목록 조회 실패 (조건: step={generation_step}, usage<{max_usage_count}, type={item_type}): {e}")
            return []

    def count_ideas(self,
                    generation_step: Optional[int] = None,
                    item_type: Optional[str] = None # 추가됨
                    ) -> int:
        """ 조건에 맞는 아이디어 개수 반환 (item_type 필터 추가) """
        sql = "SELECT COUNT(*) FROM ideas WHERE 1=1" # 기본 쿼리
        params: List[Any] = []

        if generation_step is not None:
            sql += " AND generation_step = ?"
            params.append(generation_step)
        if item_type is not None: # item_type 조건 추가
            sql += " AND item_type = ?"
            params.append(item_type)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                result = cursor.fetchone()
                # 결과가 있고, 첫 번째 값이 None이 아닌 경우 그 값을 반환, 아니면 0 반환
                return result[0] if result and result[0] is not None else 0
        except sqlite3.Error as e:
            print(f"[오류] 아이디어 개수 조회 실패 (조건: step={generation_step}, type={item_type}): {e}")
            return 0