"""Pydantic request/response models for ShadowCast API endpoints."""

from typing import Any, Dict, List, Optional

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
    image_url: str = Field(default="", max_length=1000)

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
    use_tts: bool = True
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
    use_tts: bool = True
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


class ErrorDetailItem(BaseModel):
    field: Optional[str] = None
    code: Optional[str] = None
    message: str


class ApiErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetailItem] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    error: ApiErrorBody


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class ReadinessChecks(BaseModel):
    ffmpeg: bool
    ffprobe: bool
    llm: bool
    llm_provider: str
    llm_model: str
    tts_best: str
    tts_quality: bool
    tts_providers: Dict[str, bool]
    music_beds: bool = False
    music_bed_moods: List[str] = Field(default_factory=list)
    music_beds_missing: List[str] = Field(default_factory=list)
    broll_pack: bool = False
    broll_tags: List[str] = Field(default_factory=list)
    broll_missing: List[str] = Field(default_factory=list)


class ReadinessResponse(BaseModel):
    ready: bool
    blockers: List[str]
    warnings: List[str]
    checks: ReadinessChecks
    default_video_preset: str


class MediaLibraryBucket(BaseModel):
    expected_moods: Optional[List[str]] = None
    expected_tags: Optional[List[str]] = None
    present: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    items: List[Dict[str, Any]] = Field(default_factory=list)


class MediaLibrarySummary(BaseModel):
    music_present_count: int = 0
    music_missing_count: int = 0
    broll_present_count: int = 0
    broll_missing_count: int = 0
    complete: bool = False


class MediaLibraryResponse(BaseModel):
    query: Optional[str] = None
    fetch_script: str = "scripts/fetch_operator_media.sh"
    music: MediaLibraryBucket
    broll: MediaLibraryBucket
    summary: MediaLibrarySummary


class CurrentProviderConfig(BaseModel):
    provider: str
    base_url: str
    model: str
    has_api_key: bool


class ProvidersResponse(BaseModel):
    providers: Dict[str, Any]
    current: CurrentProviderConfig


class ConfigResponse(BaseModel):
    status: str
    provider: str
    base_url: str
    model: str
    has_api_key: bool


class LLMTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    base_url: str
    detail: Optional[str] = None
    sample: Optional[str] = None


class LLMModelsResponse(BaseModel):
    provider: str
    model: str
    source: str
    models: List[str]
    count: int


class HooksResponse(BaseModel):
    hooks: List[str]
    descriptions: Dict[str, str]


class ContentStylesResponse(BaseModel):
    styles: Dict[str, Any]
    default: str


class TTSProvidersResponse(BaseModel):
    providers: Dict[str, Any]
    best: str


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    mode: str
    warnings: Optional[List[str]] = None
    product_count: Optional[int] = None
    products_found: Optional[List[str]] = None


class JobOutputSummary(BaseModel):
    videos_ready: int
    videos_expected: int
    packages_ready: int
    packages_expected: int
    warning_count: int
    is_partial: bool


class JobStatusResponse(BaseModel):
    id: str
    mode: str
    status: str
    progress: int
    current_step: str
    errors: List[str]
    warnings: List[str]
    script_errors: List[str]
    video_warnings: List[str]
    other_errors: List[str]
    summary: JobOutputSummary
    audit: Optional[Dict[str, Any]] = None
    product_count: Optional[int] = None


class JobResultsResponse(JobStatusResponse):
    product_results: Optional[List[Dict[str, Any]]] = None
    products: Optional[List[Dict[str, Any]]] = None
    hook_types: Optional[List[str]] = None
    formats: Optional[List[str]] = None
    product_info: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    trust_inputs: Optional[Any] = None


class RetryMissingResponse(BaseModel):
    job_id: str
    status: str
    message: str
    summary: JobOutputSummary


class JobAuditResponse(BaseModel):
    job_id: str
    status: Optional[str] = None
    audit: Dict[str, Any]
    summary: JobOutputSummary
