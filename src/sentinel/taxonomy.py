"""Single source of truth for the event taxonomy (keep in sync with the frontend EventType union)."""
EVENT_TYPES = [
    "Geopolitical", "Macroeconomic", "Credit Event", "Merger/Acquisition", "Product Launch",
    "Regulatory", "Supply Chain", "Cyber", "Natural Disaster", "Earnings",
]
NO_EVENT = "None"                      # internal label: relevant market commentary without a discrete event
API_NO_EVENT = "Market Commentary"     # how the API and the frontend name it
ALL_API_EVENT_TYPES = EVENT_TYPES + [API_NO_EVENT]


def api_event(label) -> str:
    """Map an internal label ('None', 'Other', missing) to a name the API and frontend can show."""
    return label if label in EVENT_TYPES else API_NO_EVENT
