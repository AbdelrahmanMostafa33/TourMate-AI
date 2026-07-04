"""Export all models so SQLAlchemy discovers them for metadata."""

from app.core.database import Base  # noqa: F401 – needed by Alembic env.py

# --- Enums (re-exported for convenience) ---
from app.models.enums import (
    TripStatus, ItineraryStatus, StopStatus, TravelMode,
    TimeOfDay,
    PlaceCategory, AccommodationType,
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
    BudgetLevel, TravelStyle, TripPace,
    FeedbackType,
    ConversationStatus, ProcessingStatus,
)

# --- Core models ---
from app.models.user import User
from app.models.trip import Trip
from app.models.profile import TripProfile
from app.models.chat import Conversation, Message

# --- Place hierarchy ---
from app.models.place import Place, HotelDetails, RestaurantDetails, AttractionDetails
from app.models.review import Review

# --- Itinerary ---
from app.models.itinerary import Itinerary, Day, ItineraryStop

# --- Booking & Payment ---
from app.models.booking import Booking, Payment, Receipt

# --- Feedback ---
from app.models.feedback import Feedback

# --- Saved places ---
from app.models.saved_place import SavedPlace

# --- System Log ---
from app.models.system_log import EventLog

# --- Image upload & features ---
from app.models.image import Image, ImageFeature
