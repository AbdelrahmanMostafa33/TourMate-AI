"""Export all models so SQLAlchemy discovers them for metadata."""

# --- Enums (re-exported for convenience) ---
from app.models.enums import (
    TripStatus, ItineraryStatus, StopStatus, TravelMode,
    StopClassification, TimeOfDay, TravelerGroupType,
    PlaceCategory,
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
    RecommendationType, RecommendationStatus,
    PaceStyle, SpendingStyle, ExperienceLean,
    DayRhythm, AttractionPreference, SocialStyle,
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

# --- Saved places & Recommendations ---
from app.models.saved_place import SavedPlace
from app.models.recommendation import Recommendation

# --- Image upload & features ---
from app.models.image import Image, ImageFeature

# --- Event log ---
from app.models.system_log import EventLog
