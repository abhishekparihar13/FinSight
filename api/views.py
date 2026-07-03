# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework.permissions import IsAuthenticated
from expenses.ml.model_service import predict_category 
from .serializers import YourDataSerializer  
from expenses.services.dataset_service import update_dataset





class PredictCategory(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        description = request.data.get("description")
        category = predict_category(description)
        return Response({"predicted_category": category})




class UpdateDataset(APIView):
    def post(self, request):
        new_data = request.data.get("new_data")

        if not new_data:
            return Response(
                {"error": "No data provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        description = new_data.get("description")
        category = new_data.get("category")

        if not description or not category:
            return Response(
                {"error": "Description and category required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            update_dataset(description, category)

            return Response(
                {"message": "Dataset updated and model retrained successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

