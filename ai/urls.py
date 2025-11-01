from django.urls import path
from .views import NLPParseAPIView, NLPResponseAPIView

urlpatterns = [
    path("nlp/parse/", NLPParseAPIView.as_view(), name="nlp-parse"),
    path("nlp/response/", NLPResponseAPIView.as_view(), name="nlp-response"),
]
