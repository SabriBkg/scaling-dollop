"""Serializers for the password reset endpoints (Story 4.5)."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=64)
    new_password = serializers.CharField(write_only=True, max_length=128)
    new_password_confirm = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        user = self.context.get("user")  # set by the view AFTER token check
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages})
        return attrs
