from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User


class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "avatar_url",
            "date_joined",
        )
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    avatar_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError("At least one field is required.")
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        user = self.user

        data["user"] = UserMeSerializer(user).data
        return data
