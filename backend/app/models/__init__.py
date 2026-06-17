"""Export all models so SQLAlchemy discovers them for metadata."""

# --- Enums (re-exported for convenience) ---
from app.models.enums import (
    TripStatus, ItineraryStatus, StopStatus, TravelMode,
    BookingType, BookingStatus, ReservationStatus,
    PaymentMethod, PaymentStatus,
    TravelDimension, FeedbackType,
    ConversationStatus, ReviewSource, ProcessingStatus,
)

# --- Core models ---
from app.models.user import User
from app.models.trip import Trip
from app.models.profile import TravelerProfile
from app.models.chat import Conversation, Message

# --- Place hierarchy ---
from app.models.place import Place, Hotel, Restaurant, Attraction, Location, OpeningHours
from app.models.review import Review

# --- Itinerary ---
from app.models.itinerary import Itinerary, Day, ItineraryStop

# --- Booking & Payment ---
from app.models.booking import Booking, Reservation, Payment, Receipt

# --- Feedback ---
from app.models.feedback import Feedback

# --- Saved places & Recommendations ---
from app.models.saved_place import SavedPlace
from app.models.recommendation import Recommendation

# --- Image upload & features ---
from app.models.image import UploadedImage, ImageFeature
