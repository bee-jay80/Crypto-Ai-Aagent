from django.urls import path
from .views import CompareAPIView, NLPToCompareAPIView

urlpatterns = [
    path("crypto/<str:asset>/compare/", CompareAPIView.as_view(), name="crypto-compare"),
    path("nlp/compare/", NLPToCompareAPIView.as_view(), name="nlp-compare"),
]
