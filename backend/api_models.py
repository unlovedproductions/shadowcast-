"""Pydantic request models for ShadowCast API endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from content_styles import DEFAULT_CONTENT_STYLE, normalize_content_style


class LLMConfigRequest(BaseModel):
    provider: str = Field(default="ollama", min_length=1, max_length=64)
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ProductInfo(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    niche: str = Field(default="General", max_length=120)
    key_features: List[str] = Field(default_factory=list, max_length=30)
    price: str = Field(default="$49.99", max_length=32)
    affiliate_link: str = Field(default="[YOUR_AFFILIATE_LINK]", max_length=500)
    keywords: List[str] = Field(default_factory=list, max_length=50)
    target_audience: str = Field(default="General consumers", max_length=200)
    product_category: str = Field(default="", max_length=120)
    competitors: List[str] = Field(default_factory=list, max_length=20)
    unique_selling_point: str = Field(default="", max_length=500)
    discount_info: str = Field(default="", max_length=200)
    coupon_code: str = Field(default="", max_length=64)
    common_complaints: str = Field(default="", max_length=4000)
    common_praises: str = Field(default="", max_length=4000)
    who_not_for: str = Field(default="", max_length=1000)
    series_name: str = Field(default="", max_length=120)
    price_comparison: str = Field(default="", max_length=500)
    content_style: str = Field(default=DEFAULT_CONTENT_STYLE, max_length=64)
    amazon_url: str = Field(default="", max_length=500)

    @field_validator("content_style")
    @classmethod
    def _normalize_style(cls, value: str) -> str:
        return normalize_content_style(value or DEFAULT_CONTENT_STYLE)

    @field_validator("key_features", "keywords", "competitors", mode="before")
    @classmethod
    def _coerce_str_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class GenerateRequest(BaseModel):
    product_info: ProductInfo
    hook_types: List[str] = Field(default_factory=lambda: ["curiosity"], min_length=1, max_length=9)
    formats: List[str] = Field(default_factory=lambda: ["short_form", "long_form"], min_length=1, max_length=2)
    content_style: str = Field(default=DEFAULT_CONTENT_STYLE, max_length=64)
    audio_enabled: bool = True
    audio_mood: str = Field(default="auto", max_length=32)
    use_tts: bool = False
    tts_provider: str = Field(default="auto", max_length=32)
    tts_voice: Optional[str] = Field(default=None, max_length=64)
    video_preset: str = Field(default="medium", max_length=32)

    @field_validator("content_style")
    @classmethod
    def _normalize_style(cls, value: str) -> str:
        return normalize_content_style(value or DEFAULT_CONTENT_STYLE)


class BatchGenerateRequest(BaseModel):
    products: List[ProductInfo] = Field(..., min_length=1, max_length=100)
    hook_types: List[str] = Field(default_factory=lambda: ["curiosity"], min_length=1, max_length=9)
    formats: List[str] = Field(default_factory=lambda: ["short_form", "long_form"], min_length=1, max_length=2)
    content_style: str = Field(default=DEFAULT_CONTENT_STYLE, max_length=64)
    audio_enabled: bool = True
    audio_mood: str = Field(default="auto", max_length=32)
    use_tts: bool = False
    tts_provider: str = Field(default="auto", max_length=32)
    tts_voice: Optional[str] = Field(default=None, max_length=64)
    video_preset: str = Field(default="medium", max_length=32)

    @field_validator("content_style")
    @classmethod
    def _normalize_style(cls, value: str) -> str:
        return normalize_content_style(value or DEFAULT_CONTENT_STYLE)


class ScrapeAmazonRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=500)

    @field_validator("url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("URL is required")
        return token


class YouTubeResearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Query is required")
        return token


class MetricRequest(BaseModel):
    video_id: str = Field(..., min_length=4, max_length=64)
    metric_type: str = Field(..., min_length=2, max_length=64)
    value: float
