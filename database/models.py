"""
SQLAlchemy ORM Models for WiFiSense Indoor Motion & CSI Fingerprinting
"""

import datetime
from sqlalchemy import Column, Integer, String, BigInteger, LargeBinary, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CSIPacket(Base):
    """
    SQLAlchemy model representing the csi_packets table.
    Stores raw CSI measurements and signal metadata received from ESP32.
    """
    __tablename__ = "csi_packets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seq_no = Column(Integer, nullable=False)
    mac = Column(String(17), nullable=False)  # format: "xx:xx:xx:xx:xx:xx"
    rssi = Column(Integer, nullable=False)
    channel = Column(Integer, nullable=False)
    bandwidth = Column(Integer, nullable=False)  # 0=20MHz, 1=40MHz
    timestamp_us = Column(BigInteger, nullable=False)
    raw_blob = Column(LargeBinary, nullable=False)  # Raw binary csi_data (128 bytes)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<CSIPacket seq={self.seq_no} mac={self.mac} rssi={self.rssi} db={self.channel}>"


class Room(Base):
    """
    Represents a physical room or space.
    """
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    blueprints = relationship("Blueprint", back_populates="room", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="room", cascade="all, delete-orphan")
    fingerprints = relationship("Fingerprint", back_populates="room", cascade="all, delete-orphan")


class Blueprint(Base):
    """
    Represents a room blueprint image and its physical dimensions.
    """
    __tablename__ = "blueprints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(500), nullable=False)
    width_px = Column(Integer, nullable=False)
    height_px = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    room = relationship("Room", back_populates="blueprints")


class Position(Base):
    """
    Represents a specific trained location/zone within a room.
    """
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(100), nullable=False)  # e.g., "Kitchen corner"
    blueprint_x = Column(Integer, nullable=True)  # Store pixel coordinates as ints or floats
    blueprint_y = Column(Integer, nullable=True)
    image_path = Column(String(500), nullable=True)

    # Relationships
    room = relationship("Room", back_populates="positions")
    fingerprints = relationship("Fingerprint", back_populates="position", cascade="all, delete-orphan")
    samples = relationship("FingerprintSample", back_populates="position", cascade="all, delete-orphan")


class Fingerprint(Base):
    """
    Represents the materialized averaged fingerprint (mean feature vector) for a position.
    """
    __tablename__ = "fingerprints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False)
    feature_vector_json = Column(String, nullable=False)  # Serialized averaged feature vector dict
    sample_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    room = relationship("Room", back_populates="fingerprints")
    position = relationship("Position", back_populates="fingerprints")


class FingerprintSample(Base):
    """
    Represents an individual fingerprint capture recording for a position.
    """
    __tablename__ = "fingerprint_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False)
    feature_vector_json = Column(String, nullable=False)  # Serialized single-window feature vector
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    position = relationship("Position", back_populates="samples")


class Event(Base):
    """
    Represents system and motion events logged to the database.
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)  # e.g., "motion_event"
    payload_json = Column(String, nullable=False)  # Serialized event details
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Event type={self.event_type} ts={self.timestamp}>"


