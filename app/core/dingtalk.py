import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

import httpx

from app.core.config import settings


# 复用 Uvicorn 的错误日志通道，确保本地控制台可看到 token 获取诊断信息。
logger = logging.getLogger("uvicorn.error")


class DingTalkError(Exception):
    """钉钉调用失败的基础异常。"""


class DingTalkConfigurationError(DingTalkError):
    """钉钉应用凭证未配置或配置不完整。"""


class DingTalkAuthenticationError(DingTalkError):
    """钉钉免登授权码无法解析为企业成员。"""


class DingTalkRequestError(DingTalkError):
    """钉钉服务不可用或返回了非预期响应。"""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code


@dataclass(frozen=True)
class DingTalkUserProfile:
    """首次登录初始化所需的钉钉员工资料。"""

    user_id: str
    name: str
    avatar_source_url: str | None
    department_ids: tuple[str, ...]


@dataclass(frozen=True)
class DingTalkDepartment:
    """首次登录初始化所需的钉钉部门资料。"""

    department_id: str
    name: str


@dataclass(frozen=True)
class DingTalkAvatar:
    """从钉钉头像地址下载并校验后的图片内容。"""

    content: bytes


class DingTalkClient:
    """企业内部 H5 微应用的钉钉服务端调用客户端。"""

    ACCESS_TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    USER_INFO_URL = "https://oapi.dingtalk.com/topapi/v2/user/getuserinfo"
    USER_DETAIL_URL = "https://oapi.dingtalk.com/topapi/v2/user/get"
    DEPARTMENT_DETAIL_URL = "https://oapi.dingtalk.com/topapi/v2/department/get"
    AVATAR_MAX_BYTES = 5 * 1024 * 1024
    AVATAR_CONTENT_TYPES = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0
        self._access_token_lock = asyncio.Lock()
        self._http_client: httpx.AsyncClient | None = None

    def is_configured(self) -> bool:
        """判断企业内部应用凭证是否完整配置。"""
        return bool(
            settings.DINGTALK_CLIENT_ID
            and settings.DINGTALK_CLIENT_SECRET
        )

    async def get_user_id_by_auth_code(self, auth_code: str) -> str:
        """使用企业内部应用 access token 将免登码解析为钉钉用户 ID。"""
        access_token = await self.get_access_token()
        response_data = await self._post_json(
            url=self.USER_INFO_URL,
            params={"access_token": access_token},
            payload={"code": auth_code},
        )

        error_code = response_data.get("errcode")
        if error_code not in (None, 0, "0"):
            raise DingTalkAuthenticationError(
                "钉钉免登授权码无效、已过期或无法用于当前应用",
            )

        result = response_data.get("result")
        if not isinstance(result, dict):
            raise DingTalkRequestError("钉钉用户信息响应格式错误")

        # 旧版接口字段为 userid；兼容部分网关返回的 userId 写法。
        user_id = result.get("userid") or result.get("userId")
        if not isinstance(user_id, str) or not user_id.strip():
            raise DingTalkAuthenticationError("钉钉响应未包含有效用户 ID")
        return user_id.strip()

    async def get_user_profile(self, user_id: str) -> DingTalkUserProfile:
        """查询员工详情，供本地用户首次初始化使用。"""
        access_token = await self.get_access_token()
        response_data = await self._post_json(
            url=self.USER_DETAIL_URL,
            params={"access_token": access_token},
            payload={"userid": user_id, "language": "zh_CN"},
        )
        result = self._get_success_result(
            response_data=response_data,
            operation_name="钉钉用户详情",
        )

        returned_user_id = self._required_string(
            result=result,
            field_name="userid",
            operation_name="钉钉用户详情",
        )
        if returned_user_id != user_id:
            raise DingTalkRequestError("钉钉用户详情与免登用户不一致")

        name = self._required_string(
            result=result,
            field_name="name",
            operation_name="钉钉用户详情",
        )
        if len(name) > 64:
            raise DingTalkRequestError("钉钉用户姓名长度超出本地限制")

        avatar_value = result.get("avatar")
        avatar_source_url = (
            avatar_value.strip() if isinstance(avatar_value, str) else None
        )

        department_values = result.get("dept_id_list")
        if not isinstance(department_values, list) or not department_values:
            raise DingTalkRequestError("钉钉用户未返回所属部门")

        department_ids: list[str] = []
        for department_value in department_values:
            if isinstance(department_value, bool):
                continue
            if isinstance(department_value, (int, str)):
                department_id = str(department_value).strip()
                if department_id:
                    department_ids.append(department_id)
        if not department_ids:
            raise DingTalkRequestError("钉钉用户未返回有效所属部门")

        return DingTalkUserProfile(
            user_id=returned_user_id,
            name=name,
            avatar_source_url=avatar_source_url or None,
            department_ids=tuple(department_ids),
        )

    async def get_department(
        self,
        department_id: str,
    ) -> DingTalkDepartment:
        """查询部门详情，供首次登录创建本地部门主数据。"""
        try:
            department_number = int(department_id)
        except ValueError as exc:
            raise DingTalkRequestError("钉钉部门 ID 格式非法") from exc

        access_token = await self.get_access_token()
        response_data = await self._post_json(
            url=self.DEPARTMENT_DETAIL_URL,
            params={"access_token": access_token},
            payload={"dept_id": department_number, "language": "zh_CN"},
        )
        result = self._get_success_result(
            response_data=response_data,
            operation_name="钉钉部门详情",
        )
        returned_department_id = str(result.get("dept_id", "")).strip()
        if returned_department_id != department_id:
            raise DingTalkRequestError("钉钉部门详情与员工所属部门不一致")

        name = self._required_string(
            result=result,
            field_name="name",
            operation_name="钉钉部门详情",
        )
        if len(name) > 64:
            raise DingTalkRequestError("钉钉部门名称长度超出本地限制")
        return DingTalkDepartment(
            department_id=returned_department_id,
            name=name,
        )

    async def download_avatar(self, avatar_source_url: str) -> DingTalkAvatar:
        """下载钉钉头像，限制协议、格式和体积后交给本地资源模块保存。"""
        parsed_url = urlparse(avatar_source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise DingTalkRequestError("钉钉头像地址格式非法")

        try:
            response = await self._get_http_client().get(
                avatar_source_url,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DingTalkRequestError(
                "下载钉钉头像时服务返回 HTTP 错误",
                http_status=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise DingTalkRequestError(
                "下载钉钉头像时发生网络错误",
                error_code=type(exc).__name__,
            ) from exc

        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if content_type.lower() not in self.AVATAR_CONTENT_TYPES:
            raise DingTalkRequestError("钉钉头像不是支持的图片格式")

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.AVATAR_MAX_BYTES:
                    raise DingTalkRequestError("钉钉头像文件过大")
            except ValueError as exc:
                raise DingTalkRequestError("钉钉头像文件大小格式错误") from exc

        avatar_content = response.content
        if not avatar_content:
            raise DingTalkRequestError("钉钉头像文件为空")
        if len(avatar_content) > self.AVATAR_MAX_BYTES:
            raise DingTalkRequestError("钉钉头像文件过大")
        return DingTalkAvatar(content=avatar_content)

    async def get_access_token(self) -> str:
        """读取有效应用 token；临近过期时由同一协程完成刷新。"""
        if not self.is_configured():
            raise DingTalkConfigurationError("钉钉 ClientId 或 ClientSecret 未配置")

        if self._has_valid_access_token():
            return self._access_token or ""

        async with self._access_token_lock:
            if self._has_valid_access_token():
                return self._access_token or ""

            response_data = await self._post_json(
                url=self.ACCESS_TOKEN_URL,
                payload={
                    # 企业内部应用服务端接口仍使用 appKey/appSecret 参数名。
                    "appKey": settings.DINGTALK_CLIENT_ID,
                    "appSecret": settings.DINGTALK_CLIENT_SECRET,
                },
            )
            access_token = response_data.get("accessToken")
            expire_in = response_data.get("expireIn")
            if not isinstance(access_token, str) or not access_token.strip():
                raise DingTalkRequestError("钉钉 access_token 响应格式错误")
            if not isinstance(expire_in, int) or expire_in <= 0:
                raise DingTalkRequestError("钉钉 access_token 有效期响应格式错误")

            self._access_token = access_token
            self._access_token_expires_at = monotonic() + expire_in
            # 仅记录可安全用于联调的元数据，禁止将 token 写入日志。
            return access_token

    async def close(self) -> None:
        """在应用关闭时释放 HTTP 连接池。"""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _has_valid_access_token(self) -> bool:
        """为网络请求预留刷新窗口，避免 token 在调用途中刚好过期。"""
        refresh_skew_seconds = max(
            settings.DINGTALK_ACCESS_TOKEN_REFRESH_SKEW_SECONDS,
            0,
        )
        return (
            self._access_token is not None
            and monotonic() < self._access_token_expires_at - refresh_skew_seconds
        )

    async def _post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """发送钉钉 JSON 请求，并统一转换网络与协议异常。"""
        try:
            response = await self._get_http_client().post(
                url,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            response_data = response.json()
        except httpx.HTTPStatusError as exc:
            raise DingTalkRequestError(
                "钉钉服务返回 HTTP 错误",
                http_status=exc.response.status_code,
                error_code=self._extract_error_code(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            raise DingTalkRequestError(
                "调用钉钉服务时发生网络错误",
                error_code=type(exc).__name__,
            ) from exc
        except ValueError as exc:
            raise DingTalkRequestError("钉钉服务返回了非 JSON 响应") from exc

        if not isinstance(response_data, dict):
            raise DingTalkRequestError("钉钉响应格式错误")
        return response_data

    def _get_success_result(
        self,
        *,
        response_data: dict[str, object],
        operation_name: str,
    ) -> dict[str, object]:
        """统一校验旧版通讯录接口的业务错误码。"""
        error_code = response_data.get("errcode")
        if error_code not in (None, 0, "0"):
            raise DingTalkRequestError(
                f"{operation_name}调用失败",
                error_code=str(error_code),
            )
        result = response_data.get("result")
        if not isinstance(result, dict):
            raise DingTalkRequestError(f"{operation_name}响应格式错误")
        return result

    def _required_string(
        self,
        *,
        result: dict[str, object],
        field_name: str,
        operation_name: str,
    ) -> str:
        value = result.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise DingTalkRequestError(
                f"{operation_name}未包含有效 {field_name}",
            )
        return value.strip()

    def _extract_error_code(self, response: httpx.Response) -> str | None:
        """仅从响应体提取可安全记录的钉钉错误码，不记录错误详情。"""
        try:
            response_data = response.json()
        except ValueError:
            return None

        if not isinstance(response_data, dict):
            return None

        error_code = response_data.get("code") or response_data.get("errcode")
        if isinstance(error_code, (str, int)):
            return str(error_code)
        return None

    def _get_http_client(self) -> httpx.AsyncClient:
        """延迟创建连接池，使未配置钉钉的本地启动不产生外部连接。"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.DINGTALK_HTTP_TIMEOUT_SECONDS),
            )
        return self._http_client


dingtalk_client = DingTalkClient()
_access_token_refresh_task: asyncio.Task[None] | None = None


async def _refresh_access_token_loop() -> None:
    """按配置间隔预热 token；登录请求仍保留按需刷新兜底。"""
    while True:
        try:
            await dingtalk_client.get_access_token()
        except DingTalkError as exc:
            # 定时任务失败不应终止应用；登录时会再次尝试获取并返回明确错误。
            # 不打印异常链，避免 request URL 中的 access_token 被日志记录。
            logger.warning(
                "dingtalk access token refresh failed: type=%s http_status=%s "
                "error_code=%s",
                type(exc).__name__,
                getattr(exc, "http_status", None),
                getattr(exc, "error_code", None),
            )

        refresh_interval_seconds = max(
            settings.DINGTALK_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS,
            1,
        )
        await asyncio.sleep(refresh_interval_seconds)


def start_dingtalk_access_token_refresh_task() -> None:
    """凭证齐全时启动应用 access token 的定时预热任务。"""
    global _access_token_refresh_task
    if not dingtalk_client.is_configured():
        return
    if _access_token_refresh_task is None or _access_token_refresh_task.done():
        _access_token_refresh_task = asyncio.create_task(
            _refresh_access_token_loop(),
        )


async def stop_dingtalk_access_token_refresh_task() -> None:
    """停止 token 刷新任务并关闭钉钉 HTTP 连接池。"""
    global _access_token_refresh_task
    if _access_token_refresh_task is not None:
        _access_token_refresh_task.cancel()
        try:
            await _access_token_refresh_task
        except asyncio.CancelledError:
            pass
        finally:
            _access_token_refresh_task = None
    await dingtalk_client.close()
