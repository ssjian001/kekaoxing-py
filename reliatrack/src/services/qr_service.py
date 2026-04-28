"""二维码生成服务 — 为样品生成 QR 码 PNG。"""

from __future__ import annotations

import base64
import io

import qrcode


def generate_qr(data: str, size: int = 8, border: int = 2) -> bytes:
    """生成 QR 码 PNG 图片并返回原始 bytes。

    Args:
        data: 编码到二维码中的文本（通常为样品 SN）。
        size: 每个模块的像素数。
        border: 边框模块数。

    Returns:
        PNG 格式图片的 bytes。
    """
    qr = qrcode.QRCode(
        version=None,           # 自动选择版本
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_base64(data: str, **kwargs: object) -> str:
    """生成 QR 码并返回 base64 编码字符串（用于存储到数据库）。

    Args:
        data: 编码到二维码中的文本。
        **kwargs: 传递给 generate_qr 的额外参数。

    Returns:
        base64 编码的 PNG 字符串。
    """
    png_bytes = generate_qr(data, **kwargs)  # type: ignore[arg-type]
    return base64.b64encode(png_bytes).decode("ascii")
