from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.department import Department
from app.models.leaderboard_snapshot import LeaderboardSnapshot
from app.models.project_upload_config import (
    MONTH_END_RECORD_TYPE,
    MONTH_START_RECORD_TYPE,
)
from app.models.proof_record import LEADERBOARD_ELIGIBLE_REVIEW_STATUSES
from app.models.season_user import SeasonUser
from app.models.user import User


class LeaderboardRepository:
    async def replace_current_season_snapshot(
        self,
        session: AsyncSession,
        season_id: int,
        required_project_count: int,
        cutoff_at: datetime,
    ) -> None:
        """全量替换当前赛季排行榜快照。"""
        # 先清理当前赛季旧快照，再重新写入，避免用户资格变化后留下脏数据。
        # 排行榜以初审结果为准；赛季结束后的终审不回溯改变赛季内打卡次数。
        await session.execute(
            text(
                """
                DELETE leaderboard_snapshot
                FROM leaderboard_snapshot
                INNER JOIN season_user
                  ON season_user.id = leaderboard_snapshot.season_user_id
                WHERE season_user.season_id = :season_id
                """
            ),
            {"season_id": season_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO leaderboard_snapshot (season_user_id, checkin_count)
                SELECT
                  season_user.id AS season_user_id,
                  COALESCE(
                    SUM(
                      CASE
                        WHEN proof_record.id IS NULL THEN 0
                        WHEN project_upload_config.record_type IN (
                          :month_start_record_type,
                          :month_end_record_type
                        ) THEN 0
                        ELSE 1
                      END
                    ),
                    0
                  )
                  + COUNT(
                    DISTINCT CASE
                      WHEN project_upload_config.record_type = :month_end_record_type
                      THEN proof_record.project_id
                    END
                  ) AS checkin_count
                FROM season_user
                LEFT JOIN proof_record
                  ON proof_record.season_user_id = season_user.id
                  AND proof_record.status = 1
                  AND proof_record.review_status IN :eligible_review_statuses
                  AND proof_record.created_at < :cutoff_at
                LEFT JOIN project_upload_config
                  ON project_upload_config.id = proof_record.project_upload_config_id
                WHERE season_user.season_id = :season_id
                  AND season_user.level_id IS NOT NULL
                  AND season_user.status >= :required_project_count
                GROUP BY season_user.id
                """
            ).bindparams(
                bindparam("eligible_review_statuses", expanding=True),
            ),
            {
                "season_id": season_id,
                "required_project_count": required_project_count,
                "cutoff_at": cutoff_at,
                "eligible_review_statuses": tuple(
                    review_status.value
                    for review_status in LEADERBOARD_ELIGIBLE_REVIEW_STATUSES
                ),
                "month_start_record_type": MONTH_START_RECORD_TYPE,
                "month_end_record_type": MONTH_END_RECORD_TYPE,
            },
        )

    async def list_current_season_snapshot(
        self,
        session: AsyncSession,
        season_id: int,
    ) -> list[tuple[str, str, str, int | None, int]]:
        """查询当前赛季排行榜快照，不在后端排序。"""
        result = await session.execute(
            select(
                User.id,
                User.name,
                Department.name,
                SeasonUser.level_id,
                LeaderboardSnapshot.checkin_count,
            )
            .select_from(LeaderboardSnapshot)
            .join(SeasonUser, SeasonUser.id == LeaderboardSnapshot.season_user_id)
            .join(User, User.id == SeasonUser.user_id)
            .join(Department, Department.id == User.department_id)
            .where(SeasonUser.season_id == season_id)
        )
        return [
            (user_id, name, department_name, level_id, checkin_count)
            for user_id, name, department_name, level_id, checkin_count in result.all()
        ]


leaderboard_repository = LeaderboardRepository()
