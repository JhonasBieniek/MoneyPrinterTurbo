"""
Bilibili (bilibili.com) video upload integration.

This service mirrors the structure of ``app/services/upload_post.py``: a config-driven
service class, a module-level singleton, and a top-level synchronous helper
(:func:`upload_to_bilibili`).

Auth is cookie-based. The user must log in to bilibili.com in a browser, open
DevTools -> Application -> Cookies, and copy ``SESSDATA``, ``bili_jct`` and
``buvid3`` into the ``bilibili_*`` config keys.

Dependency: ``bilibili-api-python`` (import name ``bilibili_api``; repo
Nemo2011/bilibili-api). The dependency is imported LAZILY inside the methods so
that importing this module (or starting the app) never crashes when the package
is not installed -- only an actual upload attempt requires it.

AI-generated-content labeling (mandatory since Bilibili's Aug 2025 policy):
    The installed ``bilibili_api.video_uploader.VideoMeta`` (v17.4.2) exposes NO
    dedicated AIGC / ai_generated / synthetic-media field -- the meta dict it
    submits to the Bilibili archive API does not carry one. Therefore this module
    labels AI content with two mechanisms:
      1. ``neutral_mark`` (创作者声明 / creator statement) on ``VideoMeta`` is set to
         the disclaimer as a best-effort "native-ish" declaration. NOTE: the
         library author marks this field's behavior as uncertain, so it should be
         verified against Bilibili's current submit API before relying on it.
      2. A clear Chinese disclaimer is appended once to the video description as a
         robust, always-present fallback.
    If a future library version adds a real AIGC field, set it here as the
    primary mechanism and keep the description fallback.
"""
import os
from typing import Optional

from loguru import logger

from app.config import config

# Appended to the description (and used as the creator statement) when AI
# labeling is enabled. Kept as a module constant so we can detect and avoid
# duplicate appends.
_AI_DISCLAIMER = "本视频部分内容由 AI 生成 (This video contains AI-generated content)."


class BilibiliService:
    # Default category id. 21 = 日常 / Daily life, a safe generic partition.
    DEFAULT_TID = 21

    @property
    def enabled(self) -> bool:
        return config.app.get("bilibili_enabled", False)

    @property
    def sessdata(self) -> str:
        return config.app.get("bilibili_sessdata", "")

    @property
    def bili_jct(self) -> str:
        return config.app.get("bilibili_bili_jct", "")

    @property
    def buvid3(self) -> str:
        return config.app.get("bilibili_buvid3", "")

    @property
    def tid(self) -> int:
        try:
            return int(config.app.get("bilibili_tid", self.DEFAULT_TID))
        except (TypeError, ValueError):
            return self.DEFAULT_TID

    @property
    def default_tags(self) -> list:
        tags = config.app.get("bilibili_tags", [])
        return list(tags) if isinstance(tags, (list, tuple)) else []

    @property
    def copyright(self) -> int:
        # 1 = original (自制), 2 = reprint (转载). Defaults to original.
        try:
            value = int(config.app.get("bilibili_copyright", 1))
        except (TypeError, ValueError):
            return 1
        return value if value in (1, 2) else 1

    @property
    def source(self) -> str:
        # Reprint source URL, required by Bilibili only when copyright == 2.
        return config.app.get("bilibili_source", "")

    @property
    def auto_upload(self) -> bool:
        return config.app.get("bilibili_auto_upload", False)

    @property
    def ai_generated_label(self) -> bool:
        return config.app.get("bilibili_ai_generated_label", True)

    @property
    def cover(self) -> str:
        return config.app.get("bilibili_cover", "")

    def is_configured(self) -> bool:
        """True only when enabled and all three auth cookies are present."""
        return bool(
            self.enabled and self.sessdata and self.bili_jct and self.buvid3
        )

    def _apply_ai_label(self, description: str) -> str:
        """Append the AI disclaimer once, never duplicating it."""
        if not self.ai_generated_label:
            return description
        if _AI_DISCLAIMER in (description or ""):
            return description
        if description:
            return f"{description}\n\n{_AI_DISCLAIMER}"
        return _AI_DISCLAIMER

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[list] = None,
        cover: Optional[str] = None,
    ) -> dict:
        if not self.is_configured():
            logger.warning("Bilibili is not configured. Skipping upload.")
            return {"success": False, "error": "Bilibili not configured"}

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return {"success": False, "error": f"Video file not found: {video_path}"}

        # Lazy import so a missing dependency never breaks module import / app start.
        try:
            import bilibili_api
            from bilibili_api import Credential, sync
            from bilibili_api.video_uploader import (
                VideoMeta,
                VideoUploader,
                VideoUploaderPage,
            )
        except ImportError as exc:
            logger.error(
                "bilibili-api-python is not installed. Run "
                "`pip install bilibili-api-python` to enable Bilibili uploads. "
                f"({exc})"
            )
            return {"success": False, "error": "bilibili-api-python not installed"}

        # Merge per-video tags with the configured defaults; de-duplicate while
        # preserving order. Bilibili requires at least one and at most ten tags.
        merged_tags: list = []
        for tag in list(tags or []) + self.default_tags:
            tag = str(tag).strip()
            if tag and tag not in merged_tags:
                merged_tags.append(tag)
        if not merged_tags:
            # A generic fallback so the API doesn't reject an empty tag list.
            merged_tags = ["AI"]
        merged_tags = merged_tags[:10]

        # Bilibili caps titles at 80 chars and descriptions at 2000 chars.
        safe_title = (title or "")[:80] or "Untitled"
        description = self._apply_ai_label(description or "")
        safe_desc = description[:2000]

        cover_path = cover or self.cover
        is_original = self.copyright == 1
        if not is_original and not self.source:
            logger.warning(
                "Bilibili copyright=2 (reprint) requires bilibili_source; "
                "none is set. Bilibili may reject the submission."
            )

        # Bilibili requires a cover image for archive submission, and this library
        # constructs VideoMeta with a mandatory cover. If none is configured we
        # cannot build a valid submission, so fail clearly instead of crashing.
        if not cover_path:
            logger.warning(
                "Bilibili upload requires a cover image. Set `bilibili_cover` to "
                "an image path (or pass cover=...). Skipping upload."
            )
            return {"success": False, "error": "Bilibili cover image required"}
        if not os.path.exists(cover_path):
            logger.error(f"Bilibili cover file not found: {cover_path}")
            return {"success": False, "error": f"Cover file not found: {cover_path}"}

        logger.info(f"Uploading video to Bilibili: {safe_title}")

        try:
            credential = Credential(
                sessdata=self.sessdata,
                bili_jct=self.bili_jct,
                buvid3=self.buvid3,
            )

            meta_kwargs = dict(
                tid=self.tid,
                title=safe_title,
                desc=safe_desc,
                cover=cover_path,
                tags=merged_tags,
                original=is_original,
            )
            if not is_original and self.source:
                meta_kwargs["source"] = self.source
            # AIGC labeling mechanism #1: creator statement (best-effort native).
            # See module docstring -- verify against the live submit API.
            if self.ai_generated_label:
                meta_kwargs["neutral_mark"] = _AI_DISCLAIMER

            meta = VideoMeta(**meta_kwargs)

            page = VideoUploaderPage(
                path=video_path,
                title=safe_title,
                description=safe_desc,
            )

            uploader = VideoUploader(
                pages=[page],
                meta=meta,
                credential=credential,
                cover=cover_path,
            )

            # The library is async; wrap with bilibili_api.sync(...) so this
            # public helper stays synchronous like upload_post.cross_post_video.
            result = sync(uploader.start())

            bvid = (result or {}).get("bvid") if isinstance(result, dict) else None
            logger.success(f"Video uploaded to Bilibili. bvid: {bvid}")
            return {"success": True, "result": result, "bvid": bvid}

        except Exception as exc:  # noqa: BLE001 - surface any upload failure
            logger.error(f"Failed to upload video to Bilibili: {exc}")
            return {"success": False, "error": str(exc)}


# Singleton instance
bilibili_service = BilibiliService()


def upload_to_bilibili(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    cover: Optional[str] = None,
) -> dict:
    return bilibili_service.upload_video(
        video_path, title, description=description, tags=tags, cover=cover
    )
