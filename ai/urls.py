from django.urls import path
from .views import A2ACryptoAPIView

urlpatterns = [
    path("a2a/crypto", A2ACryptoAPIView.as_view(), name="a2a-crypto"),
]
