import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class FlightStatus(enum.Enum):
    SCHEDULED = "scheduled"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    BOARDING = "boarding"
    DEPARTED = "departed"
    LANDED = "landed"

class RetailCategory(enum.Enum):
    FOOD = "food"
    FASHION = "fashion"
    ELECTRONICS = "electronics"
    WATCHES = "watches"
    BOOKS = "books"
    SERVICES = "services"
    AMENITY = "amenity"

class TerminalCode(enum.Enum):
    T1 = "T1"
    T2 = "T2"

class GateCode(enum.Enum):
    GATE_1 = "Gate 1"
    GATE_2 = "Gate 2"
    GATE_3 = "Gate 3"
    GATE_4 = "Gate 4"
    GATE_5 = "Gate 5"
    GATE_6 = "Gate 6"
    GATE_7 = "Gate 7"
    GATE_8 = "Gate 8"
    GATE_9 = "Gate 9"
    GATE_10 = "Gate 10"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    name = Column(String, nullable = False)
    email = Column(String, unique = True, nullable = False)
    phone_number = Column(String, nullable = True)
    created_at = Column(DateTime, default = datetime.utcnow)

    flights = relationship("Flight", back_populates="user", cascade="all, delete-orphan")


class Flight(Base):
    __tablename__ = "flights"

    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    user_id = Column(UUID(as_uuid = True), ForeignKey("users.id"), nullable = False)

    pnr = Column(String, nullable = False)
    leg_number = Column(Integer, nullable = False, default = 1)
    source = Column(String, nullable = False)
    destination = Column(String, nullable = False)
    flight_number = Column(String, nullable=False)
    airline = Column(String, nullable = False)
    aircraft = Column(String, nullable = False)

    has_layover = Column(Boolean, default = False)
    layover_airport = Column(String, nullable = True)

    departure_time_utc = Column(DateTime, nullable = False)
    arrival_time_utc = Column(DateTime, nullable = False)
    boarding_time_utc = Column(DateTime, nullable = False)
    
    baggage_belt = Column(String)

    gate_changed = Column(Boolean, default = False)

    delay_minutes = Column(Integer, default = 0)
    
    boarding_announced = Column(Boolean, default = False)

    status = Column(Enum(FlightStatus), default = FlightStatus.SCHEDULED, nullable = False)

    gate = Column(Enum(GateCode), nullable = True)
    terminal = Column(Enum(TerminalCode), nullable = True)

    is_international = Column(Boolean, default = False)

    thread_id = Column(String, nullable = True)

    user = relationship("User", back_populates="flights")


class RetailerUser(Base):
    __tablename__ = "retailer_users"

    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    
    shop_name = Column(String, nullable = False)
    terminal = Column(Enum(TerminalCode), nullable = False)
    category = Column(Enum(RetailCategory), nullable = False)

    email = Column(String, unique = True, nullable = False)
    password_hash = Column(String, nullable = False)

    offers = relationship("RetailerOffer", back_populates="retailer", cascade="all, delete-orphan")
    

class RetailerOffer(Base):
    __tablename__ = "retailer_offers"

    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    retailer_id = Column(UUID(as_uuid=True), ForeignKey("retailer_users.id"), nullable = False)

    offer_text = Column(Text, nullable = False)
    walking_node_id = Column(String, nullable = False)
    active_until = Column(DateTime, nullable = False)

    retailer = relationship("RetailerUser", back_populates="offers")