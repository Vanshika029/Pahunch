from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("PAHUNCH_DB", BASE_DIR / "data" / "pahunch.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
JWT_SECRET = os.getenv("PAHUNCH_JWT_SECRET", "development-only-change-me")
TOKEN_TTL_HOURS = 12
SCHEME_CACHE_TTL = 30
INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
_scheme_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_request_counts: dict[str, tuple[int, float]] = {}

app = FastAPI(
    title="Pahunch API",
    description="Discover public schemes, check eligibility, and track applications.",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("PAHUNCH_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DatabaseConnection:
    def __init__(self, connection: Any, postgres: bool):
        self.connection = connection
        self.postgres = postgres

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
        if self.postgres:
            statement = statement.replace("?", "%s").replace(" LIKE ", " ILIKE ")
        return self.connection.execute(statement, parameters)

    def executemany(self, statement: str, parameters: list[tuple[Any, ...]]) -> Any:
        if self.postgres:
            statement = statement.replace("?", "%s").replace(" LIKE ", " ILIKE ")
            return self.connection.cursor().executemany(statement, parameters)
        return self.connection.executemany(statement, parameters)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


@contextmanager
def connect_db() -> Iterator[DatabaseConnection]:
    if DATABASE_URL:
        raw_connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        connection = DatabaseConnection(raw_connection, postgres=True)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        raw_connection = sqlite3.connect(DB_PATH)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        connection = DatabaseConnection(raw_connection, postgres=False)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"{salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        actual = password_hash(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False


def encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def create_token(user: Any) -> str:
    now = datetime.now(timezone.utc)
    header = encode_segment(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = encode_segment(
        json.dumps(
            {
                "sub": user["id"],
                "email": user["email"],
                "role": user["role"],
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
            }
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = encode_segment(hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = encode_segment(
            hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(decoded)
        if claims.get("exp", 0) <= time.time():
            raise ValueError("Expired token")
        return claims
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from error


def initialize_database() -> None:
    if DATABASE_URL and (
        JWT_SECRET == "development-only-change-me" or len(JWT_SECRET) < 32
    ):
        raise RuntimeError("Set PAHUNCH_JWT_SECRET to a strong private value before using hosted PostgreSQL.")
    with connect_db() as db:
        integer_primary_key = (
            "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
            if DATABASE_URL
            else "INTEGER PRIMARY KEY AUTOINCREMENT"
        )
        schema = f"""
            CREATE TABLE IF NOT EXISTS users (
                id {integer_primary_key},
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'citizen' CHECK(role IN ('citizen', 'admin')),
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS profiles (
                user_id {'BIGINT' if DATABASE_URL else 'INTEGER'} PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                age INTEGER CHECK(age BETWEEN 0 AND 120),
                annual_income INTEGER CHECK(annual_income >= 0),
                state TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                gender TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS schemes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                benefit TEXT NOT NULL,
                max_income INTEGER,
                min_age INTEGER,
                max_age INTEGER,
                states TEXT NOT NULL DEFAULT '[]',
                categories TEXT NOT NULL DEFAULT '[]',
                genders TEXT NOT NULL DEFAULT '[]',
                documents TEXT NOT NULL DEFAULT '[]',
                deadline TEXT,
                featured INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS applications (
                id {integer_primary_key},
                user_id {'BIGINT' if DATABASE_URL else 'INTEGER'} NOT NULL REFERENCES users(id),
                scheme_id TEXT NOT NULL REFERENCES schemes(id),
                reference_number TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'submitted'
                    CHECK(status IN ('submitted', 'under_review', 'documents_required', 'approved', 'rejected', 'withdrawn')),
                notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, scheme_id)
            );
            CREATE TABLE IF NOT EXISTS application_events (
                id {integer_primary_key},
                application_id {'BIGINT' if DATABASE_URL else 'INTEGER'} NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_schemes_category ON schemes(category);
            CREATE INDEX IF NOT EXISTS idx_applications_user_created ON applications(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_application_events_application ON application_events(application_id, created_at);
        """
        for statement in schema.split(";"):
            if statement.strip():
                db.execute(statement)
        if db.execute("SELECT COUNT(*) AS count FROM schemes").fetchone()["count"] == 0:
            db.executemany(
                """INSERT INTO schemes
                (id, name, department, category, summary, benefit, max_income, min_age, max_age,
                 states, categories, genders, documents, deadline, featured)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("pm-kisan", "PM-KISAN Samman Nidhi", "Ministry of Agriculture", "Agriculture",
                     "Income support for eligible landholding farmer families.", "₹6,000 per year", None, 18, None,
                     "[]", "[]", "[]", json.dumps(["Aadhaar card", "Land ownership records", "Bank passbook"]),
                     "2026-12-31", 1),
                    ("ayushman-bharat", "Ayushman Bharat PM-JAY", "Ministry of Health", "Healthcare",
                     "Cashless hospital cover for eligible families at empanelled hospitals.", "Health cover up to ₹5 lakh per family", 300000, 0, None,
                     "[]", "[]", "[]", json.dumps(["Aadhaar card", "Ration card", "Income certificate"]),
                     None, 1),
                    ("pm-awas-urban", "PM Awas Yojana – Urban 2.0", "Ministry of Housing", "Housing",
                     "Support to eligible urban families seeking a pucca home.", "Housing assistance up to ₹2.5 lakh", 900000, 18, None,
                     "[]", "[]", "[]", json.dumps(["Aadhaar card", "Income certificate", "Proof of no pucca house"]),
                     "2027-03-31", 1),
                    ("sukanya-samriddhi", "Sukanya Samriddhi Yojana", "Ministry of Finance", "Education",
                     "Long-term savings account for the future of a girl child under 10.", "Tax-saving savings account with competitive interest", None, 0, 10,
                     "[]", "[]", json.dumps(["female"]), json.dumps(["Girl child's birth certificate", "Parent/guardian Aadhaar", "Address proof"]),
                     None, 0),
                    ("national-scholarship", "National Scholarship Portal", "Ministry of Education", "Education",
                     "A single-window portal for central and state student scholarships.", "Scholarship support varies by programme", 250000, 16, 30,
                     "[]", "[]", "[]", json.dumps(["Previous-year marksheet", "Income certificate", "Bank account details", "Aadhaar card"]),
                     "2026-11-30", 0),
                    ("pm-mudra", "Pradhan Mantri MUDRA Yojana", "Ministry of Finance", "Business",
                     "Loans for small businesses and micro-enterprises through lending institutions.", "Collateral-free business loans up to ₹20 lakh", None, 18, None,
                     "[]", "[]", "[]", json.dumps(["Business plan", "Identity proof", "Address proof", "Bank statements"]),
                     None, 0),
                ],
            )
        demo = db.execute("SELECT id FROM users WHERE email = ?", ("demo@pahunch.in",)).fetchone()
        if not DATABASE_URL and not demo:
            cursor = db.execute(
                "INSERT INTO users(email, password_hash, full_name) VALUES (?, ?, ?) RETURNING id",
                ("demo@pahunch.in", password_hash("Pahunch123!"), "Aarav Sharma"),
            )
            db.execute(
                "INSERT INTO profiles(user_id, age, annual_income, state, category, gender) VALUES (?, ?, ?, ?, ?, ?)",
                (cursor.fetchone()["id"], 24, 240000, "Uttar Pradesh", "General", "male"),
            )


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()


@app.middleware("http")
async def basic_rate_limit(request: Request, call_next: Any) -> Response:
    now = time.monotonic()
    key = request.client.host if request.client else "unknown"
    count, window_start = _request_counts.get(key, (0, now))
    if now - window_start >= 60:
        count, window_start = 0, now
    if count >= 120:
        return Response(
            content='{"detail":"Rate limit exceeded. Try again shortly."}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": "60"},
        )
    _request_counts[key] = (count + 1, window_start)
    return await call_next(request)


def current_user(authorization: str | None = Header(default=None)) -> Any:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue")
    claims = decode_token(authorization[7:])
    with connect_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return user


def admin_user(user: Any = Depends(current_user)) -> Any:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def profile_for(user_id: int, db: sqlite3.Connection) -> dict[str, Any]:
    row = db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return {"age": None, "annual_income": None, "state": "", "category": "", "gender": ""}
    return dict(row)


def scheme_dict(row: Any) -> dict[str, Any]:
    scheme = dict(row)
    for field in ("states", "categories", "genders", "documents"):
        scheme[field] = json.loads(scheme[field])
    scheme["featured"] = bool(scheme["featured"])
    return scheme


def eligibility_reasons(scheme: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if scheme["min_age"] is not None or scheme["max_age"] is not None:
        if profile["age"] is None:
            reasons.append("Add your age to check this scheme's criteria.")
        elif scheme["min_age"] is not None and profile["age"] < scheme["min_age"]:
            reasons.append(f"You need to be at least {scheme['min_age']} years old.")
        elif scheme["max_age"] is not None and profile["age"] > scheme["max_age"]:
            reasons.append(f"This scheme is for applicants up to {scheme['max_age']} years old.")
    if scheme["max_income"] is not None:
        if profile["annual_income"] is None:
            reasons.append("Add your annual household income to check this scheme's criteria.")
        elif profile["annual_income"] > scheme["max_income"]:
            reasons.append(f"Annual household income must be ₹{scheme['max_income']:,} or less.")
    if scheme["states"]:
        if not profile["state"]:
            reasons.append("Add your state to check this scheme's criteria.")
        elif profile["state"] not in scheme["states"]:
            reasons.append("This scheme is not available in your state.")
    if scheme["categories"]:
        if not profile["category"]:
            reasons.append("Add your social category to check this scheme's criteria.")
        elif profile["category"] not in scheme["categories"]:
            reasons.append("Your social category does not match this scheme's criteria.")
    if scheme["genders"]:
        if not profile["gender"]:
            reasons.append("Add your gender to check this scheme's criteria.")
        elif profile["gender"].lower() not in scheme["genders"]:
            reasons.append("This scheme is not available for the selected gender.")
    return reasons


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    age: int | None = Field(default=None, ge=0, le=120)
    annual_income: int | None = Field(default=None, ge=0, le=100_000_000)
    state: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=40)
    gender: str = Field(default="", max_length=30)


class ApplicationInput(BaseModel):
    scheme_id: str = Field(min_length=1, max_length=80)
    notes: str = Field(default="", max_length=1000)


class StatusInput(BaseModel):
    status: str
    message: str = Field(min_length=3, max_length=500)


class AssistantInput(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Pahunch API", "version": "1.0.0"}


@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterInput) -> dict[str, Any]:
    with connect_db() as db:
        try:
            cursor = db.execute(
                "INSERT INTO users(email, password_hash, full_name) VALUES (?, ?, ?) RETURNING id",
                (payload.email.lower(), password_hash(payload.password), payload.full_name),
            )
        except INTEGRITY_ERRORS as error:
            raise HTTPException(status_code=409, detail="An account with this email already exists") from error
        user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.fetchone()["id"],)).fetchone()
        db.execute("INSERT INTO profiles(user_id) VALUES (?)", (user["id"],))
        return {"access_token": create_token(user), "token_type": "bearer", "user": user_summary(user, db)}


@app.post("/api/v1/auth/login")
def login(payload: LoginInput) -> dict[str, Any]:
    with connect_db() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
        if not user or not password_matches(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
        return {"access_token": create_token(user), "token_type": "bearer", "user": user_summary(user, db)}


def user_summary(user: Any, db: DatabaseConnection) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "profile": profile_for(user["id"], db),
    }


@app.get("/api/v1/auth/me")
def me(user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        return user_summary(user, db)


@app.get("/api/v1/profile")
def get_profile(user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        return profile_for(user["id"], db)


@app.put("/api/v1/profile")
def update_profile(payload: ProfileInput, user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        db.execute(
            """INSERT INTO profiles(user_id, age, annual_income, state, category, gender, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET age=excluded.age, annual_income=excluded.annual_income,
            state=excluded.state, category=excluded.category, gender=excluded.gender, updated_at=CURRENT_TIMESTAMP""",
            (user["id"], payload.age, payload.annual_income, payload.state, payload.category, payload.gender),
        )
        return profile_for(user["id"], db)


@app.get("/api/v1/schemes")
def list_schemes(
    response: Response,
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    sort: str = Query(default="featured", pattern="^(featured|name|deadline)$"),
    user: Any = Depends(current_user),
) -> dict[str, Any]:
    cache_key = f"{q.lower()}|{category.lower()}|{page}|{page_size}|{sort}"
    now = time.monotonic()
    cached = _scheme_cache.get(cache_key)
    if cached and cached[0] > now:
        rows = cached[1]
    else:
        ordering = {"featured": "featured DESC, name", "name": "LOWER(name)", "deadline": "deadline IS NULL, deadline"}
        conditions = []
        params: list[Any] = []
        if q:
            conditions.append("(name LIKE ? OR summary LIKE ? OR department LIKE ?)")
            wildcard = f"%{q}%"
            params.extend([wildcard, wildcard, wildcard])
        if category:
            conditions.append("LOWER(category) = LOWER(?)")
            params.append(category)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with connect_db() as db:
            records = db.execute(
                f"SELECT * FROM schemes{where} ORDER BY {ordering[sort]} LIMIT 500",
                params,
            ).fetchall()
        rows = [scheme_dict(record) for record in records]
        _scheme_cache[cache_key] = (now + SCHEME_CACHE_TTL, rows)
    with connect_db() as db:
        profile = profile_for(user["id"], db)
        applied = {
            record["scheme_id"]
            for record in db.execute("SELECT scheme_id FROM applications WHERE user_id = ?", (user["id"],)).fetchall()
        }
    enriched = []
    for scheme in rows:
        reasons = eligibility_reasons(scheme, profile)
        enriched.append({**scheme, "eligible": not reasons, "eligibility_reasons": reasons, "applied": scheme["id"] in applied})
    total = len(enriched)
    start = (page - 1) * page_size
    response.headers["Cache-Control"] = f"private, max-age={SCHEME_CACHE_TTL}"
    return {"items": enriched[start : start + page_size], "page": page, "page_size": page_size, "total": total}


@app.get("/api/v1/schemes/{scheme_id}")
def get_scheme(scheme_id: str, user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        row = db.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scheme not found")
        scheme = scheme_dict(row)
        profile = profile_for(user["id"], db)
        applied = db.execute(
            "SELECT 1 FROM applications WHERE user_id = ? AND scheme_id = ?", (user["id"], scheme_id)
        ).fetchone()
        reasons = eligibility_reasons(scheme, profile)
        return {**scheme, "eligible": not reasons, "eligibility_reasons": reasons, "applied": bool(applied)}


@app.get("/api/v1/eligibility")
def eligibility(user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        profile = profile_for(user["id"], db)
        schemes = [scheme_dict(row) for row in db.execute("SELECT * FROM schemes ORDER BY featured DESC, name").fetchall()]
        matches = []
        for scheme in schemes:
            reasons = eligibility_reasons(scheme, profile)
            matches.append({**scheme, "eligible": not reasons, "eligibility_reasons": reasons})
    return {"profile_complete": all(profile.get(field) not in (None, "") for field in ("age", "annual_income", "state")), "eligible_count": sum(item["eligible"] for item in matches), "schemes": matches}


def application_view(record: Any, db: DatabaseConnection) -> dict[str, Any]:
    events = db.execute(
        "SELECT status, message, created_at FROM application_events WHERE application_id = ? ORDER BY created_at, id",
        (record["id"],),
    ).fetchall()
    return {
        **dict(record),
        "documents": json.loads(record["documents"]),
        "timeline": [dict(event) for event in events],
    }


@app.get("/api/v1/applications")
def list_applications(user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        records = db.execute(
            """SELECT a.*, s.name AS scheme_name, s.department, s.documents
            FROM applications a JOIN schemes s ON s.id = a.scheme_id
            WHERE a.user_id = ? ORDER BY a.created_at DESC, a.id DESC""",
            (user["id"],),
        ).fetchall()
        return {"items": [application_view(record, db) for record in records], "total": len(records)}


@app.post("/api/v1/applications", status_code=201)
def create_application(payload: ApplicationInput, user: Any = Depends(current_user)) -> dict[str, Any]:
    with connect_db() as db:
        row = db.execute("SELECT * FROM schemes WHERE id = ?", (payload.scheme_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scheme not found")
        scheme = scheme_dict(row)
        reasons = eligibility_reasons(scheme, profile_for(user["id"], db))
        if reasons:
            raise HTTPException(status_code=422, detail={"message": "Update your profile to meet this scheme's criteria", "eligibility_reasons": reasons})
        reference = f"PAH-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"
        try:
            cursor = db.execute(
                "INSERT INTO applications(user_id, scheme_id, reference_number, notes) VALUES (?, ?, ?, ?) RETURNING id",
                (user["id"], scheme["id"], reference, payload.notes),
            )
        except INTEGRITY_ERRORS as error:
            raise HTTPException(status_code=409, detail="You already have an application for this scheme") from error
        application_id = cursor.fetchone()["id"]
        db.execute(
            "INSERT INTO application_events(application_id, status, message) VALUES (?, 'submitted', ?)",
            (application_id, "Application received. Keep your reference number to track progress."),
        )
        record = db.execute(
            """SELECT a.*, s.name AS scheme_name, s.department, s.documents
            FROM applications a JOIN schemes s ON s.id = a.scheme_id WHERE a.id = ?""",
            (application_id,),
        ).fetchone()
        return application_view(record, db)


@app.patch("/api/v1/applications/{application_id}")
def withdraw_application(
    application_id: int,
    user: Any = Depends(current_user),
) -> dict[str, Any]:
    with connect_db() as db:
        record = db.execute(
            "SELECT id, status FROM applications WHERE id = ? AND user_id = ?", (application_id, user["id"])
        ).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Application not found")
        if record["status"] in ("approved", "rejected", "withdrawn"):
            raise HTTPException(status_code=409, detail="This application can no longer be withdrawn")
        db.execute(
            "UPDATE applications SET status = 'withdrawn', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (application_id,),
        )
        db.execute(
            "INSERT INTO application_events(application_id, status, message) VALUES (?, 'withdrawn', ?)",
            (application_id, "Application withdrawn by the applicant."),
        )
        updated = db.execute(
            """SELECT a.*, s.name AS scheme_name, s.department, s.documents
            FROM applications a JOIN schemes s ON s.id = a.scheme_id WHERE a.id = ?""",
            (application_id,),
        ).fetchone()
        return application_view(updated, db)


@app.patch("/api/v1/admin/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    payload: StatusInput,
    user: Any = Depends(admin_user),
) -> dict[str, Any]:
    allowed = {"under_review", "documents_required", "approved", "rejected"}
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
    with connect_db() as db:
        record = db.execute("SELECT id FROM applications WHERE id = ?", (application_id,)).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Application not found")
        db.execute(
            "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload.status, application_id),
        )
        db.execute(
            "INSERT INTO application_events(application_id, status, message) VALUES (?, ?, ?)",
            (application_id, payload.status, payload.message),
        )
        updated = db.execute(
            """SELECT a.*, s.name AS scheme_name, s.department, s.documents
            FROM applications a JOIN schemes s ON s.id = a.scheme_id WHERE a.id = ?""",
            (application_id,),
        ).fetchone()
        return application_view(updated, db)


@app.post("/api/v1/assistant/chat")
def assistant_chat(payload: AssistantInput, user: Any = Depends(current_user)) -> dict[str, Any]:
    message = payload.message.lower()
    with connect_db() as db:
        profile = profile_for(user["id"], db)
        schemes = [scheme_dict(row) for row in db.execute("SELECT * FROM schemes ORDER BY featured DESC, name").fetchall()]
    matches = [
        scheme for scheme in schemes
        if any(word in f"{scheme['name']} {scheme['category']} {scheme['summary']}".lower() for word in message.split() if len(word) > 3)
    ]
    if any(term in message for term in ("eligible", "match", "for me", "recommend")):
        eligible = [scheme for scheme in schemes if not eligibility_reasons(scheme, profile)]
        names = ", ".join(scheme["name"] for scheme in eligible[:4]) or "no schemes yet"
        reply = f"Based on the details in your profile, you may be eligible for {names}. Check each scheme's official criteria before applying."
        references = [scheme["id"] for scheme in eligible[:4]]
    elif matches:
        scheme = matches[0]
        reply = f"{scheme['name']} is offered by the {scheme['department']}. {scheme['summary']} The listed benefit is {scheme['benefit']}. Required documents: {', '.join(scheme['documents'])}. Please verify current rules on the official government portal."
        references = [scheme["id"]]
    elif any(term in message for term in ("document", "documents", "paper", "bring")):
        reply = "Documents vary by scheme. Open a scheme card to see its checklist. Common items include Aadhaar, proof of residence, an income certificate, and bank account details."
        references = []
    elif any(term in message for term in ("track", "status", "application")):
        reply = "Open My applications to see your reference number, latest status, and the full update timeline. Keep your reference number for any official follow-up."
        references = []
    else:
        reply = "I can help you find eligible schemes, explain benefits and document checklists, or track an application. Tell me your question or ask about a scheme by name."
        references = []
    return {"reply": reply, "scheme_ids": references, "assistant_mode": "rules-based demo"}
