"""report_service: 신고 관련 비즈니스 로직을 처리하는 서비스."""

from typing import Dict, List, Optional, Tuple

from models import report_models, post_models, comment_models
from utils.formatters import format_datetime
from utils.exceptions import not_found_error, bad_request_error


class ReportService:
    """신고 관리 서비스."""

    @staticmethod
    async def create_report(
        reporter_id: int,
        target_type: str,
        target_id: int,
        reason: str,
        description: Optional[str],
        timestamp: str,
    ) -> Dict:
        """신고를 생성합니다."""
        # 1. 대상 존재 확인
        if target_type == "post":
            target = await post_models.get_post_by_id(target_id)
            if not target:
                raise not_found_error("post", timestamp)
            # 자기 게시글 신고 방지
            if target.author_id == reporter_id:
                raise bad_request_error(
                    "cannot_report_own_content",
                    timestamp,
                    "자신의 게시글은 신고할 수 없습니다.",
                )
        elif target_type == "comment":
            target = await comment_models.get_comment_by_id(target_id)
            if not target:
                raise not_found_error("comment", timestamp)
            # 자기 댓글 신고 방지
            if target.author_id == reporter_id:
                raise bad_request_error(
                    "cannot_report_own_content",
                    timestamp,
                    "자신의 댓글은 신고할 수 없습니다.",
                )

        # 2. 신고 생성 (IntegrityError는 controller에서 처리)
        report = await report_models.create_report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            description=description,
        )

        return {
            "report_id": report.id,
            "target_type": report.target_type,
            "target_id": report.target_id,
            "reason": report.reason,
            "status": report.status,
        }

    @staticmethod
    async def get_reports(
        status: Optional[str],
        offset: int,
        limit: int,
    ) -> Tuple[List[Dict], int, bool]:
        """신고 목록 조회 및 가공."""
        reports_data = await report_models.get_reports(
            status=status, offset=offset, limit=limit,
        )
        total_count = await report_models.get_reports_count(status=status)
        has_more = offset + limit < total_count

        for report in reports_data:
            report["created_at"] = format_datetime(report["created_at"])
            report["resolved_at"] = format_datetime(report.get("resolved_at"))

        return reports_data, total_count, has_more

    @staticmethod
    async def resolve_report(
        report_id: int,
        admin_id: int,
        new_status: str,
        timestamp: str,
    ) -> Dict:
        """신고를 처리합니다.

        resolved: 대상 콘텐츠를 soft delete합니다.
        dismissed: 대상을 유지합니다.
        """
        # 1. 신고 존재 확인
        report = await report_models.get_report_by_id(report_id)
        if not report:
            raise not_found_error("report", timestamp)

        if report.status != "pending":
            raise bad_request_error(
                "already_processed",
                timestamp,
                "이미 처리된 신고입니다.",
            )

        # 2. 신고 처리
        resolved = await report_models.resolve_report(report_id, admin_id, new_status)
        if not resolved:
            raise not_found_error("report", timestamp)

        # 3. resolved인 경우 대상 콘텐츠 soft delete
        # NOTE: resolve_report와 soft delete는 별도 트랜잭션으로 실행됨.
        # resolve 후 delete 실패 시 관리자가 수동으로 삭제해야 함.
        if new_status == "resolved":
            if report.target_type == "post":
                await post_models.delete_post(report.target_id)
            elif report.target_type == "comment":
                await comment_models.delete_comment(report.target_id)

        return {
            "report_id": resolved.id,
            "status": resolved.status,
            "resolved_by": resolved.resolved_by,
        }
