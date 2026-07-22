from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.department import Department


class DepartmentRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        department_id: str,
    ) -> Department | None:
        """根据部门 ID 查询部门主数据。"""
        result = await session.execute(
            select(Department).where(Department.id == department_id),
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> Department | None:
        """用于识别部门名称唯一约束冲突，避免错误关联到其他部门。"""
        result = await session.execute(
            select(Department).where(Department.name == name),
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        department: Department,
    ) -> Department:
        """创建钉钉同步得到的部门主数据。"""
        session.add(department)
        await session.flush()
        return department


department_repository = DepartmentRepository()
