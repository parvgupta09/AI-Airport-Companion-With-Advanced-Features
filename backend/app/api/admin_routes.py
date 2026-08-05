import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.security import get_passoword_hash, verify_password, create_session_token
from app.database.postgres_session import get_db
from app.database.postgres_models import (
    RetailerUser,
    RetailerOffer,
    RetailCategory,
    TerminalCode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Retailer & Admin Panel"])

class RetailerCreateRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=300)
    terminal: TerminalCode = Field(..., description="T1 or T2")
    category: RetailCategory = Field(..., description="food, fashion, electronics, books, watches, services, amenity")
    email: EmailStr
    password: str = Field(..., min_length=6)

class RetailerResponse(BaseModel):
    id: uuid.UUID
    shop_name: str
    terminal: str
    category: str
    email: str

    class config:
        from_attributes = True

class OfferCreateRequest(BaseModel):
    retailer_i: uuid.UUID = Field(..., description="UUID of the RetailerUser creating the offer")
    offer_text: str = Field(..., min_length=5, description="The promotional text/deal")
    walking_node_id: str = Field(..., description="Graph node ID where this shop is located")
    active_until: datetime = Field(..., description="UTC expiration time fo the deal")

class OfferResponse(BaseModel):
    id: uuid.UUID
    retailer_id: uuid.UUID
    shop_name: str
    terminal: str
    category: str
    offer_text: str
    walking_node: str
    active_until: str

class OfferListResponse(BaseModel):
    success: bool
    count: int
    offers: List[OfferResponse]

class RetailerLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Retailer shop email")
    password: str = Field(..., description="Plaintext Password")

class RetailerLoginResponse(BaseModel):
    success: bool
    message: str
    token: str
    retailer_id: uuid.UUID
    shop_name: str
    terminal: str
    category: str


@router.post("/retailers", response_model=RetailerResponse, status_code=status.HTTP_201_CREATED)
async def create_retailer(payload: RetailerCreateRequest, db: Session = Depends(get_db)):
    """
    Registers a new airport shop/retailer in the system
    """

    existing_retailer = db.query(RetailerUser).filter(
        RetailerUser.email == payload.email.lower().strip()
    ).first()

    if existing_retailer:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A retailer with this email is already registered.")

    try:
        new_retailer = RetailerUser(
            shop_name=payload.shop_name.strip(),
            terminal=payload.terminal,
            category=payload.category,
            email=payload.email.lower().strip(),
            password_hash=get_passoword_hash(payload.password)
        )

        db.add(new_retailer)
        db.commit()
        db.refresh(new_retailer)

        logger.info(f"Retailer '{new_retailer.shop_name}' registered successfully.")

        return RetailerResponse(
            id = new_retailer.id,
            shop_name = new_retailer.shop_name,
            terminal = new_retailer.terminal.value,
            category = new_retailer.category.value,
            email = new_retailer.email
        )

    except Exception as e:
        logger.info(f"Error registering retailer: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to register shop.")


@router.post("/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(payload: OfferCreateRequest, db: Session = Depends(get_db)):
    """
    Creates a new promotional offer tied to a specific retailer and graph node.
    """

    retailer = db.query(RetailerUser).filter(RetailerUser.id == payload.retailer_id).first()

    if not retailer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retailer shop not found for the provided retailer_id")

    try:
        new_offer = RetailerOffer(
            retailer_id=retailer.id,
            offer_text=payload.offer_text.strip(),
            walking_node_id=payload.walking_node_id,
            active_until=payload.active_until
        )

        db.add(new_offer)
        db.commit()
        db.refresh(new_offer)

        return OfferResponse(
            id = new_offer.id,
            retailer_id = retailer.id,
            shop_name = retailer.shop_name,
            terminal = retailer.terminal.value,
            category = retailer.category.value,
            offer_text = new_offer.offer_text,
            walking_node_id = new_offer.walking_node_id,
            active_until = new_offer.active_until
        )

    except Exception as e:
        logger.error(f"Error creating offer: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create promotional offer.")


@router.get("/offers", response_model=OfferListResponse)
async def get_offers(terminal: Optional[TerminalCode] = Query(default=None, description="Filter by T1 or T2"), category: Optional[RetailCategory] = Query(default=None, description="Filter by retail category"), active_only: bool = Query(default = True, description="Only return unexpired category"), db: Session = Depends(get_db)):
    """
    Returns all offers joined with their RetailerUser details
    Used by RetailerAdminPanel.tsx AND AI Langgraph recommendation tool.
    """

    query = db.query(RetailerOffer).join(RetailerUser, RetailerOffer.retailer_id == RetailerUser.id)

    if terminal:
        query = query.filter(RetailerUser.terminal == terminal)

    if category:
        query = query.filter(RetailerUser.category == category)

    if active_only:
        now = datetime.now(timezone.utc)
        query = query.filter(RetailerOffer.active_until >= now)

    offers = query.order_by(RetailerOffer.active_until.asc()).all()

    response_list = [
        OfferResponse(
            id = offer.id,
            retailer_id = offer.retailer.id,
            shop_name = offer.retailer.shop_name,
            terminal = offer.retailer.terminal.value,
            category = offer.retailer.category.value,
            offer_text = offer.offer_text,
            walking_node_id = offer.walking_node_id,
            active_until = offer.active_until
        )
        for offer in offers
    ]

    return OfferResponse(
        success = True,
        count = len(response_list),
        offers = response_list
    )

@router.delete("/offers/{offer_id}", status_code=status.HTTP_200_OK)
async def delete_offer(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Permanently deletes a promotional offer by UUID.
    """

    offer = db.query(RetailerOffer).filter(RetailerOffer.id == offer_id).first()

    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

    try:
        db.delete(offer)
        db.commit()

        logger.info(f"Offer UUID {offer_id} deleted successfully.")
        return {"success": True, "message": "Offer deleted successfully."}

    except Exception as e:
        logger.error(f"Error deleting offer UUID {offer_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete promotional offer.")

@router.post("/login", response_model=RetailerLoginResponse)
async def login_retailer(payload: RetailerLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a retailer using email and password.
    Returns a session token to access and manage promotional offer in RetailerAdminPanel.tsx.
    """

    retailer = db.query(RetailerUser).filter(RetailerUser.email == payload.email.lower().strip()).first()

    if not retailer or not verify_password(payload.password, retailer.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email and password")

    # Used the same create_session_token as we used for the 
    admin_token = create_session_token(
        user_id = str(retailer.id),
        flight_id = "ADMIN_SESSION",
        thread_id = f"retailer_{retailer.shop_name}",
        departure_time_utc = datetime.now(timezone.utc),
        arrival_time_utc = datetime.now(timezone.utc)
    )

    logger.info(f"Retailer '{retailer.shop_name}' logged in successfully.")

    return RetailerLoginResponse(
        success = True,
        message = "Login Successful",
        token = admin_token,
        retailer_id = retailer.id,
        shop_name = retailer.shop_name,
        terminal = retailer.terminal.value,
        category = retailer.category.value
    )