from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TelegramAuthRequest(BaseModel):
    init_data: str
    project_id: int | None = None


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: int
    status: str
    store_id: int
    is_test: bool
    original_url: str | None = None
    mask_url: str | None = None
    illumination_url: str | None = None
    specular_url: str | None = None
    result_url: str | None = None
    wall_area_sqm: float | None = None
    selected_color_id: int | None = None
    selected_decor_color_id: int | None = None
    selected_material_id: int | None = None
    selected_finish: str | None = None
    editor_mode: str | None = "paint"
    error_message: str | None = None
    created_at: datetime
    expires_at: datetime


class BrandPackSizeOut(BaseModel):
    id: int
    brand_id: int
    volume_liters: float
    price_uah: float
    label: str | None = None
    sort_order: int = 0
    active: bool = True

    model_config = {"from_attributes": True}


class BrandPackSizeIn(BaseModel):
    id: int | None = None
    volume_liters: float = Field(gt=0)
    price_uah: float = Field(gt=0)
    label: str | None = None
    sort_order: int = 0
    active: bool = True


class BrandOut(BaseModel):
    id: int
    name: str
    logo: str | None
    country: str | None
    coverage_sqm_per_liter: float = 10.0
    recommended_coats: int = 2
    paint_finish: str = "matte"
    paint_finish_label: str = "Матова"
    active: bool
    pack_sizes: list[BrandPackSizeOut] = []
    discount_percent: float | None = None

    model_config = {"from_attributes": True}


class PaintPackLineOut(BaseModel):
    label: str
    volume_liters: float
    price_uah: float
    count: int
    line_total_uah: float


class PaintEstimateOut(BaseModel):
    area_sqm: float
    coats: int
    coverage_sqm_per_liter: float
    waste_percent: float
    liters_needed: float
    tint_base: str | None = None
    base_surcharge_percent: float
    packs: list[PaintPackLineOut]
    packs_subtotal_uah: float
    base_surcharge_uah: float
    total_uah: float
    summary_short: str
    summary_detail: str
    discount_percent: float | None = None


class ColorOut(BaseModel):
    id: int
    brand_id: int
    name: str
    hex: str
    manufacturer_code: str | None
    category: str
    tint_base: str | None = None
    base_surcharge_percent: float = 0.0
    price_per_sqm: float | None = None
    original_price_per_sqm: float | None = None
    discount_percent: float | None = None
    in_stock: bool = True
    active: bool

    model_config = {"from_attributes": True}

    @field_validator("category", mode="before")
    @classmethod
    def _category_str(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)


class ColorListResponse(BaseModel):
    items: list[ColorOut]
    total: int
    page: int
    page_size: int


class DecorativeMaterialOut(BaseModel):
    id: int
    store_id: int
    name: str
    brand_id: int | None
    category: str | None
    texture_url: str | None
    preview_url: str | None
    texture_scale: float
    recommended_coats: int = 1
    in_stock: bool = True
    active: bool
    pack_sizes: list["DecorativeMaterialPackSizeOut"] = []
    discount_percent: float | None = None

    model_config = {"from_attributes": True}


class DecorativeMaterialPackSizeOut(BaseModel):
    id: int
    coverage_sqm: float
    price_uah: float
    label: str | None = None
    sort_order: int = 0
    active: bool = True

    model_config = {"from_attributes": True}


class DecorativeMaterialPackSizeIn(BaseModel):
    id: int | None = None
    coverage_sqm: float = Field(gt=0)
    price_uah: float = Field(gt=0)
    label: str | None = None
    sort_order: int | None = None


class DecorativeColorOut(BaseModel):
    id: int
    material_id: int
    name: str
    hex: str
    price_per_sqm: float | None = None
    original_price_per_sqm: float | None = None
    discount_percent: float | None = None
    in_stock: bool = True
    active: bool

    model_config = {"from_attributes": True}


class BrandCreate(BaseModel):
    name: str
    logo: str | None = None
    country: str | None = None
    coverage_sqm_per_liter: float = Field(default=10.0, gt=0)
    recommended_coats: int = Field(default=2, ge=1, le=5)
    paint_finish: str = Field(default="matte", pattern=r"^(matte|silk_matte|gloss)$")
    active: bool = True
    pack_sizes: list[BrandPackSizeIn] = []


class BrandUpdate(BaseModel):
    name: str | None = None
    logo: str | None = None
    country: str | None = None
    coverage_sqm_per_liter: float | None = Field(default=None, gt=0)
    recommended_coats: int | None = Field(default=None, ge=1, le=5)
    paint_finish: str | None = Field(default=None, pattern=r"^(matte|silk_matte|gloss)$")
    active: bool | None = None
    pack_sizes: list[BrandPackSizeIn] | None = None


class ColorCreate(BaseModel):
    brand_id: int
    name: str
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    manufacturer_code: str | None = None
    category: str
    tint_base: str | None = Field(default=None, pattern=r"^[ABCabc]$")
    base_surcharge_percent: float | None = None
    price_per_sqm: float | None = None
    active: bool = True


class ColorUpdate(BaseModel):
    name: str | None = None
    hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    manufacturer_code: str | None = None
    category: str | None = None
    tint_base: str | None = Field(default=None, pattern=r"^[ABCabc]$")
    base_surcharge_percent: float | None = None
    price_per_sqm: float | None = None
    in_stock: bool | None = None
    active: bool | None = None


class StockUpdate(BaseModel):
    in_stock: bool


class MaterialCreate(BaseModel):
    name: str
    brand_id: int | None = None
    category: str | None = None
    texture_scale: float = 1.0
    recommended_coats: int = Field(default=1, ge=1, le=5)
    active: bool = True
    pack_sizes: list[DecorativeMaterialPackSizeIn] = []


class MaterialUpdate(BaseModel):
    name: str | None = None
    brand_id: int | None = None
    category: str | None = None
    texture_scale: float | None = None
    recommended_coats: int | None = Field(default=None, ge=1, le=5)
    in_stock: bool | None = None
    active: bool | None = None
    pack_sizes: list[DecorativeMaterialPackSizeIn] | None = None


class DecorativeColorCreate(BaseModel):
    name: str
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    price_per_sqm: float | None = None
    in_stock: bool = True
    active: bool = True


class DecorativeColorUpdate(BaseModel):
    name: str | None = None
    hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    price_per_sqm: float | None = Field(default=None, ge=0)
    in_stock: bool | None = None


class ImportPreviewRow(BaseModel):
    name: str
    hex: str
    manufacturer_code: str | None
    category: str
    brand_name: str
    valid: bool
    error: str | None = None


class ImportPreviewResponse(BaseModel):
    rows: list[ImportPreviewRow]
    valid_count: int
    invalid_count: int


class ImportConfirmRequest(BaseModel):
    brand_id: int
    rows: list[ImportPreviewRow]


class PaintFinish(str, Enum):
    MATTE = "matte"
    SILK_MATTE = "silk_matte"
    GLOSS = "gloss"


class StorePublicOut(BaseModel):
    id: int
    name: str
    slug: str
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None

    model_config = {"from_attributes": True}


class StoreSettingsUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None
    manager_telegram_chat_id: int | None = None
    leads_group_chat_id: int | None = None
    crew_telegram_chat_id: int | None = None
    telegram_bot_token: str | None = None
    business_open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    business_close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    business_timezone: str | None = None


class StoreSettingsOut(BaseModel):
    id: int
    name: str
    slug: str
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None
    manager_telegram_chat_id: int | None = None
    leads_group_chat_id: int | None = None
    crew_telegram_chat_id: int | None = None
    business_open_time: str = "09:00"
    business_close_time: str = "19:00"
    business_timezone: str = "Europe/Kyiv"
    has_bot_token: bool = False
    bot_token_hint: str | None = None

    model_config = {"from_attributes": True}


class ProjectStateUpdate(BaseModel):
    wall_area_sqm: float | None = None
    selected_color_id: int | None = None
    selected_decor_color_id: int | None = None
    selected_material_id: int | None = None
    selected_finish: str | None = None
    mode: str | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("paint", "decor"):
            raise ValueError("mode must be paint or decor")
        return v


class LeadCreate(BaseModel):
    project_id: int
    phone: str = Field(min_length=7, max_length=30)
    customer_name: str | None = None
    comment: str | None = None


class LeadOut(BaseModel):
    id: int
    project_id: int
    phone: str
    customer_name: str | None
    telegram_username: str | None = None
    comment: str | None
    wall_area_sqm: float | None
    estimated_total_uah: float | None
    selection_summary: str | None
    paint_plan_summary: str | None = None
    original_url: str | None = None
    result_url: str | None = None
    is_test: bool = False
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("status", mode="before")
    @classmethod
    def _status_str(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)


class LeadCreateResponse(LeadOut):
    telegram_notified: bool = False
    customer_ack_text: str | None = None
    customer_notified: bool = False


class LeadStatusUpdate(BaseModel):
    status: str


class LeadCustomerMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class BroadcastAudienceOut(BaseModel):
    count: int


class BroadcastOut(BaseModel):
    id: int
    title: str
    body: str
    image_url: str | None = None
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AdminStatsOut(BaseModel):
    period_days: int | None = None
    projects_total: int
    projects_real: int
    projects_test: int
    editor_opens: int
    leads_total: int
    leads_new: int
    downloads_estimate: int
    funnel_uploads: int = 0
    funnel_editor: int = 0
    funnel_leads: int = 0
    funnel_contacted: int = 0
    funnel_closed: int = 0
    funnel_rate_upload_to_editor: float | None = None
    funnel_rate_editor_to_lead: float | None = None
    funnel_rate_lead_to_contacted: float | None = None
    funnel_rate_contacted_to_closed: float | None = None


class AdminProjectOut(BaseModel):
    id: int
    status: str
    is_test: bool
    wall_area_sqm: float | None
    selection_summary: str | None
    estimated_total_uah: float | None
    editor_opens: int
    user_name: str | None
    user_phone_hint: str | None
    original_url: str | None
    result_url: str | None
    created_at: datetime


class PlatformStoreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    telegram_bot_token: str | None = None
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None
    admin_email: EmailStr | None = None
    admin_password: str | None = Field(default=None, min_length=6)


class PlatformStoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    telegram_bot_token: str | None = None
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None
    manager_telegram_chat_id: int | None = None
    leads_group_chat_id: int | None = None
    active: bool | None = None


class PlatformStoreOut(BaseModel):
    id: int
    name: str
    slug: str
    phone: str | None = None
    address: str | None = None
    telegram_username: str | None = None
    manager_telegram_chat_id: int | None = None
    leads_group_chat_id: int | None = None
    active: bool
    has_bot_token: bool = False
    bot_token_hint: str | None = None
    admins_count: int = 0
    projects_count: int = 0
    leads_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformStoreAdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "owner"


class PlatformStoreAdminUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    role: str | None = None
    active: bool | None = None


class PlatformStoreAdminOut(BaseModel):
    id: int
    store_id: int
    email: str
    role: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("role", mode="before")
    @classmethod
    def _role_str(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)


class PlatformStatsOut(BaseModel):
    stores_total: int
    stores_active: int
    projects_total: int
    leads_total: int
    leads_new: int


class StoreDiscountOut(BaseModel):
    id: int
    scope: str
    target_id: int | None = None
    target_label: str | None = None
    discount_percent: float
    label: str | None = None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreDiscountCreate(BaseModel):
    scope: str
    target_id: int | None = None
    discount_percent: float = Field(gt=0, le=100)
    label: str | None = None


class BulkPriceAdjustIn(BaseModel):
    scope: str
    target_id: int | None = None
    mode: str
    value: float = Field(gt=0)


class BulkPriceAdjustOut(BaseModel):
    updated_count: int
    store_colors: int = 0
    brand_packs: int = 0
    decor_colors: int = 0
    decor_packs: int = 0
    message: str


class CatalogPromotionOut(BaseModel):
    scope: str
    discount_percent: float
    message: str
    target_label: str | None = None
