import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [e.value for e in enum_cls]


class ProjectStatus(str, enum.Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CLOSED = "closed"


class BroadcastStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    PARTIAL = "partial"
    FAILED = "failed"


class AdminRole(str, enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"


class ColorCategory(str, enum.Enum):
    WHITE = "Білі"
    GREY = "Сірі"
    BEIGE = "Бежеві"
    BROWN = "Коричневі"
    GREEN = "Зелені"
    BLUE = "Сині"
    YELLOW = "Жовті"
    RED = "Червоні"
    DARK = "Темні"
    PASTEL = "Пастельні"


class PaintFinish(str, enum.Enum):
    MATTE = "matte"
    SILK_MATTE = "silk_matte"
    GLOSS = "gloss"


PAINT_FINISH_LABELS: dict[str, str] = {
    PaintFinish.MATTE.value: "Матова",
    PaintFinish.SILK_MATTE.value: "Шовк.-матова",
    PaintFinish.GLOSS.value: "Глянцева",
}


class DiscountScope(str, enum.Enum):
    ALL = "all"
    PAINT = "paint"
    DECOR = "decor"
    BRAND = "brand"
    COLOR = "color"
    MATERIAL = "material"
    DECOR_COLOR = "decor_color"


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    telegram_bot_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    telegram_username: Mapped[str | None] = mapped_column(String(100))
    manager_telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    leads_group_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    crew_telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    admins: Mapped[list["StoreAdmin"]] = relationship(back_populates="store")
    projects: Mapped[list["Project"]] = relationship(back_populates="store")
    decorative_materials: Mapped[list["DecorativeMaterial"]] = relationship(back_populates="store")
    leads: Mapped[list["Lead"]] = relationship(back_populates="store")
    store_colors: Mapped[list["StoreColor"]] = relationship(back_populates="store")
    store_brands: Mapped[list["StoreBrand"]] = relationship(back_populates="store")
    broadcasts: Mapped[list["StoreBroadcast"]] = relationship(back_populates="store")
    discounts: Mapped[list["StoreDiscount"]] = relationship(back_populates="store")
    brand_pack_prices: Mapped[list["StoreBrandPackPrice"]] = relationship(back_populates="store")


class StoreAdmin(Base):
    __tablename__ = "store_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, values_callable=_enum_values, name="adminrole"),
        default=AdminRole.EDITOR,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="admins")


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list["Project"]] = relationship(back_populates="user")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    original_image: Mapped[str | None] = mapped_column(String(500))
    mask_image: Mapped[str | None] = mapped_column(String(500))
    illumination_image: Mapped[str | None] = mapped_column(String(500))
    specular_image: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, values_callable=_enum_values, name="projectstatus"),
        default=ProjectStatus.RECEIVED,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_bot_id: Mapped[int | None] = mapped_column(BigInteger)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    wall_area_sqm: Mapped[float | None] = mapped_column(Float)
    editor_opens: Mapped[int] = mapped_column(default=0)
    selected_color_id: Mapped[int | None] = mapped_column(ForeignKey("colors.id"))
    selected_decor_color_id: Mapped[int | None] = mapped_column(ForeignKey("decorative_colors.id"))
    selected_material_id: Mapped[int | None] = mapped_column(ForeignKey("decorative_materials.id"))
    selected_finish: Mapped[str | None] = mapped_column(String(20))
    editor_mode: Mapped[str | None] = mapped_column(String(10), default="paint")
    result_image: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="projects")
    store: Mapped["Store"] = relationship(back_populates="projects")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    logo: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(100))
    coverage_sqm_per_liter: Mapped[float] = mapped_column(Float, default=10.0)
    recommended_coats: Mapped[int] = mapped_column(default=2)
    paint_finish: Mapped[str] = mapped_column(String(20), default=PaintFinish.MATTE.value)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    colors: Mapped[list["Color"]] = relationship(back_populates="brand")
    pack_sizes: Mapped[list["BrandPackSize"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    store_brands: Mapped[list["StoreBrand"]] = relationship(back_populates="brand", cascade="all, delete-orphan")


class BrandPackSize(Base):
    __tablename__ = "brand_pack_sizes"
    __table_args__ = (Index("ix_brand_pack_sizes_brand", "brand_id", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    price_uah: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="pack_sizes")
    store_prices: Mapped[list["StoreBrandPackPrice"]] = relationship(back_populates="brand_pack_size")


class StoreBrandPackPrice(Base):
    __tablename__ = "store_brand_pack_prices"
    __table_args__ = (
        Index("ix_store_brand_pack_prices_store", "store_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    brand_pack_size_id: Mapped[int] = mapped_column(
        ForeignKey("brand_pack_sizes.id", ondelete="CASCADE"),
        nullable=False,
    )
    price_uah: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="brand_pack_prices")
    brand_pack_size: Mapped["BrandPackSize"] = relationship(back_populates="store_prices")


class Color(Base):
    __tablename__ = "colors"
    __table_args__ = (
        Index("ix_colors_brand_category_active", "brand_id", "category", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hex: Mapped[str] = mapped_column(String(7), nullable=False)
    manufacturer_code: Mapped[str | None] = mapped_column(String(100))
    tint_base: Mapped[str | None] = mapped_column(String(1))
    base_surcharge_percent: Mapped[float] = mapped_column(Float, default=0.0)
    price_per_sqm: Mapped[float | None] = mapped_column(Float)
    category: Mapped[ColorCategory] = mapped_column(
        Enum(ColorCategory, values_callable=_enum_values, name="colorcategory"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="colors")
    store_colors: Mapped[list["StoreColor"]] = relationship(back_populates="color")


class StoreColor(Base):
    __tablename__ = "store_colors"
    __table_args__ = (
        Index("ix_store_colors_store_active", "store_id", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    color_id: Mapped[int] = mapped_column(ForeignKey("colors.id"), nullable=False)
    price_per_sqm: Mapped[float | None] = mapped_column(Float)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="store_colors")
    color: Mapped["Color"] = relationship(back_populates="store_colors")


class StoreBrand(Base):
    __tablename__ = "store_brands"
    __table_args__ = (
        Index("ix_store_brands_store_active", "store_id", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="store_brands")
    brand: Mapped["Brand"] = relationship(back_populates="store_brands")


class DecorativeMaterial(Base):
    __tablename__ = "decorative_materials"
    __table_args__ = (
        Index("ix_decorative_materials_store_active", "store_id", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100))
    texture_file: Mapped[str | None] = mapped_column(String(500))
    preview_image: Mapped[str | None] = mapped_column(String(500))
    texture_scale: Mapped[float] = mapped_column(Float, default=1.0)
    recommended_coats: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="decorative_materials")
    brand: Mapped["Brand | None"] = relationship()
    colors: Mapped[list["DecorativeColor"]] = relationship(back_populates="material")
    pack_sizes: Mapped[list["DecorativeMaterialPackSize"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )


class DecorativeMaterialPackSize(Base):
    __tablename__ = "decorative_material_pack_sizes"
    __table_args__ = (Index("ix_decor_material_packs_material", "material_id", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("decorative_materials.id", ondelete="CASCADE"), nullable=False
    )
    coverage_sqm: Mapped[float] = mapped_column(Float, nullable=False)
    price_uah: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material: Mapped["DecorativeMaterial"] = relationship(back_populates="pack_sizes")


class DecorativeColor(Base):
    __tablename__ = "decorative_colors"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("decorative_materials.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hex: Mapped[str] = mapped_column(String(7), nullable=False)
    price_per_sqm: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material: Mapped["DecorativeMaterial"] = relationship(back_populates="colors")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_store_status", "store_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(Text)
    wall_area_sqm: Mapped[float | None] = mapped_column(Float)
    estimated_total_uah: Mapped[float | None] = mapped_column(Float)
    selection_summary: Mapped[str | None] = mapped_column(String(500))
    paint_plan_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, values_callable=_enum_values, name="leadstatus"),
        default=LeadStatus.NEW,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="leads")
    project: Mapped["Project"] = relationship()
    user: Mapped["User"] = relationship()


class StoreBroadcast(Base):
    __tablename__ = "store_broadcasts"
    __table_args__ = (Index("ix_store_broadcasts_store_created", "store_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("store_admins.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default=BroadcastStatus.QUEUED.value)
    total_recipients: Mapped[int] = mapped_column(default=0)
    sent_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    store: Mapped["Store"] = relationship(back_populates="broadcasts")
    created_by: Mapped["StoreAdmin | None"] = relationship()


class StoreDiscount(Base):
    __tablename__ = "store_discounts"
    __table_args__ = (Index("ix_store_discounts_store_active", "store_id", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped["Store"] = relationship(back_populates="discounts")
